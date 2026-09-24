"""Committed-artifact checks for the IRS Optional Sales Tax Tables scope (TY2022-2025).

The tables are the ones the Secretary prescribes under 26 U.S.C. 164(b)(5)(H),
printed in each year's Instructions for Schedule A (Form 1040). The digests pinned
below were computed from an independent parse of the same PDFs (poppler
``pdftotext -layout`` and MuPDF word boxes agreed on every cell for all four years;
for TY2025 the irs.gov HTML edition also agreed), so these tests fail if a body
loses, reorders or misreads any table cell.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import fitz
import pytest
import yaml

from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION = "2026-09-24-irs-optional-sales-tax-tables-ty2022-2025"
MANIFEST_PATH = REPO_ROOT / "manifests/us-irs-optional-sales-tax-tables-ty2022-2025.yaml"
YEARS = (2022, 2023, 2024, 2025)
SLICE_SLUGS = (
    "line-5a-general-sales-taxes",
    "optional-state-sales-tax-tables",
    "optional-local-sales-tax-table-selector",
    "optional-local-sales-tax-tables",
)
SOURCE_SHA256 = {
    2022: "7fab0861b94e075f9e60f8b8c9e23b234e5b0dccae37b7025847e9806e3e8f08",
    2023: "63a8e9171defdfc6aa7380d9c4e4f168984f8a50cb4352fe7d62994fb455428e",
    2024: "a8d762028c317629e841e4b600a1f6d55b41a9b778bce7e07726205187d3a599",
    2025: "b0999b12d9dc4b13868501a9c1879011c00d2fc035f13a1391251d355a6242c8",
}
# sha256 of json.dumps(obj, sort_keys=True, separators=(",", ":")) where obj is
# {state: [[six values] per bracket]} (state), {state: [footnotes, rate]} (headers)
# or {"A".."D": [[six values] per bracket]} (local).
DIGESTS = {
    2022: {
        "state": "7fa09926d74b4e5687e9c6781e986a24975f3839964be8495b45a60af46c381c",
        "headers": "c2c20e817c9416e870c0aeb1e5f39cb89a79aa8a6ae9007ebb39fea34a612cca",
        "local": "dbfab40f6470fef2a325da6a9fdd80b5bf89885bd071bb08c7d451cf6fadc669",
    },
    2023: {
        "state": "0a8ea7b8d72a3f6629bd8122d5334e7b0e3959f1bf4189ac71bba9901345e1fc",
        "headers": "410761dd496963e16264033ff7a233889fdd35ecb47d609db57fd299913ba670",
        "local": "8b6de46b9edfed89f222779e36e58bea9f63bba3005602a8e6be6cf5caccc224",
    },
    2024: {
        "state": "d813fc0994bcf9526f1ae5f89a41b1b45574544283e994d288e4ed201cd7af97",
        "headers": "aa0ee80b32c1f51a44cea56e8e4ea855b08be7eede82b156c03673b1c55a2d24",
        "local": "ff5b20883b01935dc791aeabc920d4a27604158bfac0688d30525cabf05e9d3c",
    },
    2025: {
        "state": "6bc1842f95b2d1e73685a55260062cd375474faf52ae3fc93b11a5359f62163a",
        "headers": "2d74d405d2d2efc0f1aa66c234bbf1fa91203387840a48beed93425aeae43f48",
        "local": "914f91958ffe3f0e7c323674b6606aa0b2101df5724d5b2d1469da85ba910ff4",
    },
}
STATES = {
    "Alabama": "AL",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "District of Columbia": "DC",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
}
BRACKETS = [
    (0, 20000),
    (20000, 30000),
    (30000, 40000),
    (40000, 50000),
    (50000, 60000),
    (60000, 70000),
    (70000, 80000),
    (80000, 90000),
    (90000, 100000),
    (100000, 120000),
    (120000, 140000),
    (140000, 160000),
    (160000, 180000),
    (180000, 200000),
    (200000, 225000),
    (225000, 250000),
    (250000, 275000),
    (275000, 300000),
    (300000, None),
]
# Worksheet line 2: states whose residents take the base local amount from the
# Optional Local Sales Tax Tables. TY2022 lists neither Alabama nor Kansas; both
# carry footnote 1 (ratio method) in the TY2022 state table and footnote 2 from
# TY2023.
_LINE_2_FROM_2023 = (
    "Alabama, Alaska, Arizona, Arkansas, Colorado, Georgia, Illinois, Kansas, "
    "Louisiana, Mississippi, Missouri, New York, North Carolina, South Carolina, "
    "Tennessee, Utah, or Virginia"
)
LINE_2_STATES = {
    2022: (
        "Alaska, Arizona, Arkansas, Colorado, Georgia, Illinois, Louisiana, "
        "Mississippi, Missouri, New York, North Carolina, South Carolina, Tennessee, "
        "Utah, or Virginia"
    ),
    2023: _LINE_2_FROM_2023,
    2024: _LINE_2_FROM_2023,
    2025: _LINE_2_FROM_2023,
}
PYMUPDF_VERSION = "1.26.7"
_HEADER_RE = re.compile(
    r"((?:[A-Z][a-z]+ )*?[A-Z][a-z]+(?: of [A-Z][a-z]+)?) (\d(?:,\d)*) (\d+\.\d+)%"
)
_BOUND = r"\$?(\d{1,3}(?:,\d{3})+|0)"


def _provisions() -> dict[str, dict[str, object]]:
    path = REPO_ROOT / f"data/corpus/provisions/us/form/{VERSION}.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines()]
    return {str(record["citation_path"]): record for record in records}


def _root(year: int, slug: str) -> str:
    return f"us/form/irs/ty{year}/i1040sca-{slug}"


def _body(year: int, slug: str) -> str:
    body = _provisions()[f"{_root(year, slug)}/document-1"]["body"]
    assert isinstance(body, str)
    return body


def _digest(obj: object) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _state_name(text: str) -> str | None:
    words = text.split()
    for k in range(len(words)):
        name = " ".join(words[k:])
        if name in STATES:
            return name
    return None


def _state_table(year: int) -> dict[str, dict[str, object]]:
    """Rebuild the state table from the body's tokens.

    Each block header names up to three states as '<State> <footnotes> <rate>%';
    each of the block's 19 rows is '$lower $upper' (or '$lower or more') followed by
    six values per state in header order. The parse reads whitespace-normalized
    text, so a row the position sort appends to a note line is still found.
    """
    text = " ".join(_body(year, "optional-state-sales-tax-tables").split())
    headers = [
        (m.start(), STATES[name], [int(x) for x in m.group(2).split(",")], float(m.group(3)))
        for m in _HEADER_RE.finditer(text)
        if (name := _state_name(m.group(1)))
    ]
    blocks: list[list[tuple[int, str, list[int], float]]] = []
    for header in headers:
        if blocks and header[0] - blocks[-1][-1][0] <= 120:
            blocks[-1].append(header)
        else:
            blocks.append([header])
    table: dict[str, dict[str, object]] = {}
    for index, block in enumerate(blocks):
        end = blocks[index + 1][0][0] if index + 1 < len(blocks) else len(text)
        segment = text[block[-1][0] : end]
        width = 6 * len(block)
        rows = re.findall(
            _BOUND + r" (?:" + _BOUND + r"|or more)((?: \d+){" + str(width) + r"})(?!\d)",
            segment,
        )
        assert len(rows) == 19, (year, [header[1] for header in block], len(rows))
        for position, (_, code, footnotes, rate) in enumerate(block):
            table[code] = {
                "footnotes": footnotes,
                "rate": rate,
                "bounds": [
                    (int(low.replace(",", "")), int(high.replace(",", "")) if high else None)
                    for low, high, _ in rows
                ],
                "values": [
                    [int(value) for value in values.split()][6 * position : 6 * position + 6]
                    for _, _, values in rows
                ],
            }
    return table


def _local_tables(year: int) -> dict[str, list[list[int]]]:
    text = " ".join(_body(year, "optional-local-sales-tax-tables").split())
    rows = re.findall(_BOUND + r" (?:" + _BOUND + r"|or more)((?: \d+){24})(?!\d)", text)
    assert len(rows) == 19, (year, len(rows))
    assert [
        (int(low.replace(",", "")), int(high.replace(",", "")) if high else None)
        for low, high, _ in rows
    ] == BRACKETS
    return {
        letter: [
            [int(value) for value in values.split()][6 * k : 6 * k + 6] for _, _, values in rows
        ]
        for k, letter in enumerate("ABCD")
    }


def test_sources_are_the_official_pdf_bytes() -> None:
    source_dir = REPO_ROOT / f"data/corpus/sources/us/form/{VERSION}/official-documents"
    for year in YEARS:
        for slug in SLICE_SLUGS:
            source = source_dir / f"irs-i1040sca-ty{year}-{slug}.pdf"
            assert hashlib.sha256(source.read_bytes()).hexdigest() == SOURCE_SHA256[year]
    inventory = json.loads(
        (REPO_ROOT / f"data/corpus/inventory/us/form/{VERSION}.json").read_text()
    )
    items = inventory["items"]
    assert len(items) == 32
    for item in items:
        year = int(re.search(r"/ty(\d{4})/", item["citation_path"]).group(1))
        assert item["source_url"] == f"https://www.irs.gov/pub/irs-prior/i1040sca--{year}.pdf"
        assert item["sha256"] == SOURCE_SHA256[year]
        assert item["metadata"]["source_sha256"] == SOURCE_SHA256[year]
        assert item["metadata"]["primary_source"] is True


def test_coverage_is_complete() -> None:
    coverage = json.loads((REPO_ROOT / f"data/corpus/coverage/us/form/{VERSION}.json").read_text())
    assert coverage == {
        "complete": True,
        "document_class": "form",
        "duplicate_provision_citations": [],
        "duplicate_source_citations": [],
        "extra_provisions": [],
        "jurisdiction": "us",
        "matched_count": 32,
        "missing_from_provisions": [],
        "provision_count": 32,
        "source_count": 32,
        "version": VERSION,
    }
    expected = []
    for year in YEARS:
        for slug in SLICE_SLUGS:
            expected.extend([_root(year, slug), f"{_root(year, slug)}/document-1"])
    assert list(_provisions()) == expected
    for year in YEARS:
        for slug in SLICE_SLUGS:
            assert _provisions()[_root(year, slug)]["expression_date"] == f"{year}-01-01"


def test_state_tables_match_the_independent_parse() -> None:
    for year in YEARS:
        table = _state_table(year)
        assert sorted(table) == sorted(STATES.values())
        for code, entry in table.items():
            assert entry["bounds"] == BRACKETS, (year, code)
        assert (
            _digest({code: entry["values"] for code, entry in table.items()})
            == (DIGESTS[year]["state"])
        ), year
        assert (
            _digest({code: [entry["footnotes"], entry["rate"]] for code, entry in table.items()})
            == DIGESTS[year]["headers"]
        ), year


def test_state_table_spot_cells() -> None:
    """Cells read off the printed pages (Texas, $80,000-$90,000, family size 2)."""
    assert [_state_table(year)["TX"]["values"][7][1] for year in YEARS] == [
        1001,
        1152,
        972,
        987,
    ]
    assert _state_table(2023)["AL"]["values"][0] == [365, 436, 485, 523, 555, 600]
    assert _state_table(2025)["WY"]["values"][18] == [1047, 1193, 1290, 1365, 1426, 1511]
    assert _state_table(2025)["LA"]["rate"] == 5.0
    assert _state_table(2024)["LA"]["rate"] == 4.45


def test_state_tables_exclude_states_without_a_general_sales_tax() -> None:
    for year in YEARS:
        body = _body(year, "optional-state-sales-tax-tables")
        for name in ("Alaska", "Delaware", "Montana", "New Hampshire", "Oregon"):
            assert f"{name} " not in re.sub(r"Residents of Alaska", "", body), (year, name)
        assert "Residents of Alaska do not have a state sales tax" in " ".join(body.split())


def test_tables_are_non_decreasing_in_family_size_and_income() -> None:
    for year in YEARS:
        grids = {code: entry["values"] for code, entry in _state_table(year).items()}
        grids.update({f"local {k}": v for k, v in _local_tables(year).items()})
        for name, grid in grids.items():
            for row in grid:
                assert row == sorted(row), (year, name, row)
            for size in range(6):
                column = [row[size] for row in grid]
                assert column == sorted(column), (year, name, size)


def test_local_tables_match_the_independent_parse() -> None:
    for year in YEARS:
        assert _digest(_local_tables(year)) == DIGESTS[year]["local"], year
        body = " ".join(_body(year, "optional-local-sales-tax-tables").split())
        assert body.startswith(f"{year} Optional Local Sales Tax Tables")
        # Local Table D is printed as 25% of the New York state table.
        assert "Local Table D" in body


def test_local_table_selector_is_the_selector_only() -> None:
    for year in YEARS:
        body = _body(year, "optional-local-sales-tax-table-selector")
        assert body.startswith("Which Optional Local Sales Tax Table Should I Use?")
        assert "* Note: Local Table D is just 25% of the NY State table." in body
        assert f"{year} Optional Local Sales Tax Tables" not in body
        assert not re.search(r"\$0 \$20,000", body)
        for state in ("Alaska", "Arizona", "Colorado", "New York", "South Carolina"):
            assert state in body, (year, state)
    # Stream order keeps the South Carolina county lists readable.
    assert "Chesterfield\nCounty, Colleton County, Darlington County" in _body(
        2022, "optional-local-sales-tax-table-selector"
    )


def test_line_5a_slices_carry_the_worksheet() -> None:
    for year in YEARS:
        body = _body(year, "line-5a-general-sales-taxes")
        flat = " ".join(body.split())
        assert body.splitlines()[0] == "Line 5a"
        assert "Line 5b" not in body.splitlines()
        assert (
            f"Enter your state general sales taxes from the {year} Optional State Sales Tax Table"
            in flat
        )
        assert (
            "you lived only in Connecticut, the District of Columbia, Indiana, Kentucky, Maine, Maryland, Massachusetts, Michigan, New Jersey, or Rhode Island"
            in flat
        )
        assert f"Did you live in {LINE_2_STATES[year]} in {year}?" in flat
        assert "Deduction for general sales taxes. Add lines 1, 6, and 7." in flat
        assert "Optional Sales Tax Tables" in flat


def test_local_table_footnote_matches_worksheet_line_2() -> None:
    """The states footnoted '2' (use the local tables) are the line 2 states less Alaska."""
    for year in YEARS:
        footnoted = {code for code, entry in _state_table(year).items() if 2 in entry["footnotes"]}
        listed = {
            STATES[name.removeprefix("or ").strip()]
            for name in LINE_2_STATES[year].split(", ")
            if name.removeprefix("or ").strip() != "Alaska"
        }
        assert footnoted == listed, (year, footnoted ^ listed)


def test_no_local_tax_footnote_matches_worksheet_skip_list() -> None:
    """The states footnoted '4' (no local general sales tax) are the worksheet's
    'skip lines 2 through 5' jurisdictions."""
    skip = {"CT", "DC", "IN", "KY", "ME", "MD", "MA", "MI", "NJ", "RI"}
    for year in YEARS:
        footnoted = {code for code, entry in _state_table(year).items() if 4 in entry["footnotes"]}
        assert footnoted == skip, (year, footnoted ^ skip)


def test_slices_record_the_text_extractor() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]
    assert len(documents) == 16
    for document in documents:
        assert document["metadata"]["text_extractor"] == f"PyMuPDF {PYMUPDF_VERSION}"
        metadata = _provisions()[document["citation_path"]]["metadata"]
        assert metadata["text_extractor"] == f"PyMuPDF {PYMUPDF_VERSION}"


def _window_tokens(pdf: fitz.Document, window: dict[str, object], sort: bool) -> list[str]:
    lines: list[str] = []
    for page_number in range(int(window["start_page"]), int(window["end_page"]) + 1):
        lines.extend(
            line.strip()
            for line in pdf[page_number - 1].get_text("text", sort=sort).splitlines()
            if line.strip()
        )
    start = window.get("start_at_pattern")
    stop = window.get("stop_at_pattern")
    if start:
        lines = lines[next(i for i, line in enumerate(lines) if re.search(str(start), line)) :]
    if stop:
        hits = [i for i, line in enumerate(lines) if re.search(str(stop), line)]
        lines = lines[: hits[0]] if hits else lines
    return " ".join(lines).split()


@pytest.mark.skipif(
    fitz.VersionBind != PYMUPDF_VERSION,
    reason=f"the bodies were extracted with PyMuPDF {PYMUPDF_VERSION}",
)
def test_slice_bodies_keep_every_pdf_token() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]
    source_dir = REPO_ROOT / f"data/corpus/sources/us/form/{VERSION}/official-documents"
    by_path = _provisions()
    for document in documents:
        extraction = document["extraction"]
        with fitz.open(source_dir / f"{document['source_id']}.pdf") as pdf:
            tokens: list[str] = []
            for window in extraction["page_windows"]:
                tokens.extend(_window_tokens(pdf, window, bool(extraction.get("sort_text"))))
        body = by_path[f"{document['citation_path']}/document-1"]["body"]
        assert str(body).split() == tokens, document["source_id"]


def test_statutory_cross_reference_resolves() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]
    versions = {document["metadata"]["statutory_corpus_version"] for document in documents}
    assert len(versions) == 1
    path = REPO_ROOT / f"data/corpus/provisions/us/statute/{versions.pop()}.jsonl"
    record = next(
        json.loads(line)
        for line in path.read_text().splitlines()
        if '"citation_path": "us/statute/26/164"' in line
    )
    assert "(H) Amount of deduction may be determined under tables" in record["body"]
    assert "the amount determined under tables prescribed by the Secretary" in record["body"]
    for document in documents:
        assert document["metadata"]["statutory_corpus_citation"] == "us/statute/26/164"


def test_scope_passes_release_validation() -> None:
    release = ReleaseManifest(
        name="us-2026-09-24-irs-optional-sales-tax-tables-validation",
        quality_profile="complete-expression-dates-v1",
        scopes=(ReleaseScope("us", "form", VERSION),),
    )
    report = validate_release(REPO_ROOT / "data/corpus", release, strict_warnings=True)
    assert report.to_mapping()["ok"] is True
    assert report.to_mapping()["issue_count"] == 0
