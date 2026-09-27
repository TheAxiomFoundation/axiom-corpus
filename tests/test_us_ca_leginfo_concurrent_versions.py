"""Committed-artifact checks for the concurrent LegInfo versions scope (2026-09-26).

The scope carries every version California LegInfo listed on 2026-09-26 for the
four multi-version sections the corpus carries (WIC 11450, WIC 11451.5, R&TC
17552.3, R&TC 17563.5), each at its ``<section>--<slug>`` variant path. See
docs/ingest-runs/2026-09-26-us-ca-leginfo-concurrent-versions.md.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import shutil
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.california_versions import (
    leginfo_page_version,
    leginfo_variant_slug,
    parse_leginfo_picker,
)
from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.corpus.states import (
    _california_html_history,
    _california_html_section_body,
    extract_california_code_sections,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data/corpus"
PREFIX = "2026-09-26-ca-leginfo-concurrent-versions"
SPECS = ("WIC:11450@all", "WIC:11451.5@all", "RTC:17552.3@all", "RTC:17563.5@all")
VERSION = (
    f"{PREFIX}-us-ca-sections-wic-11450--all-wic-11451.5--all-rtc-17552.3--all-rtc-17563.5--all"
)
SOURCES = CORPUS_ROOT / f"sources/us-ca/statute/{VERSION}"
CALWORKS_VERSION = (
    "2026-06-25-ca-wic-calworks-us-ca-sections-wic-11450-wic-11450.12-wic-11451.5-wic-11452"
    "-wic-11452.018"
)
CHAPTER_VERSION = "2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7"
# citation path -> (op_statues, op_chapter, op_section, dated clauses), in picker order.
EXPECTED = {
    "us-ca/statute/wic/11450--operative-2021-07-01": (
        "2024",
        "798",
        "1",
        {"operative": "2021-07-01", "inoperative": "2024-07-01"},
    ),
    "us-ca/statute/wic/11450--operative-2024-07-01": (
        "2026",
        "310",
        "2",
        {"operative": "2024-07-01"},
    ),
    "us-ca/statute/wic/11451.5--repealed-2020-06-01": (
        "2019",
        "27",
        "59",
        {"repealed": "2020-06-01"},
    ),
    "us-ca/statute/wic/11451.5--operative-2020-06-01": (
        "2022",
        "588",
        "5",
        {"operative": "2020-06-01", "inoperative": "2024-10-01"},
    ),
    "us-ca/statute/wic/11451.5--operative-2024-10-01": (
        "2022",
        "588",
        "6",
        {"operative": "2024-10-01"},
    ),
    "us-ca/statute/rtc/17552.3--stats-2002-ch-34-sec-22": ("2002", "34", "22", {}),
    "us-ca/statute/rtc/17552.3--stats-2002-ch-35-sec-22": ("2002", "35", "22", {}),
    "us-ca/statute/rtc/17563.5--stats-2002-ch-34-sec-24": ("2002", "34", "24", {}),
    "us-ca/statute/rtc/17563.5--stats-2002-ch-35-sec-24": ("2002", "35", "24", {}),
}
# The version each merged carrier holds at the plain path (same op triple and sectionuid).
PLAIN_PATH_VERSIONS = {
    "us-ca/statute/wic/11450": "us-ca/statute/wic/11450--operative-2021-07-01",
    "us-ca/statute/wic/11451.5": "us-ca/statute/wic/11451.5--operative-2024-10-01",
    "us-ca/statute/rtc/17552.3": "us-ca/statute/rtc/17552.3--stats-2002-ch-34-sec-22",
    "us-ca/statute/rtc/17563.5": "us-ca/statute/rtc/17563.5--stats-2002-ch-35-sec-24",
}


def _jsonl(version: str) -> list[dict]:
    path = CORPUS_ROOT / f"provisions/us-ca/statute/{version}.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


def _rows() -> dict[str, dict]:
    return {row["citation_path"]: row for row in _jsonl(VERSION)}


def _source(row: dict) -> Path:
    return CORPUS_ROOT / row["source_path"]


def _table_body(html: bytes) -> str:
    soup = BeautifulSoup(html, "html.parser")
    body = _california_html_section_body(
        soup.find(id="single_law_section") or soup, preserve_tables=True
    )
    assert body is not None
    return body


def test_the_scope_carries_one_variant_row_per_listed_version() -> None:
    rows = _rows()
    assert list(rows) == list(EXPECTED)
    for path, row in rows.items():
        op_statues, op_chapter, op_section, clauses = EXPECTED[path]
        metadata = row["metadata"]
        section, variant = path.rsplit("/", 1)[1].split("--")
        assert (metadata["op_statues"], metadata["op_chapter"], metadata["op_section"]) == (
            op_statues,
            op_chapter,
            op_section,
        )
        assert "status" not in metadata
        assert {kind: c["date"] for kind, c in metadata["leginfo_note_clauses"].items()} == clauses
        assert metadata["leginfo_version_count"] == len(metadata["variant_citation_paths"])
        assert metadata["variant"] == row["identifiers"]["california:variant"] == variant
        assert metadata["canonical_citation_path"] == path.split("--")[0]
        assert row["identifiers"]["california:section"] == section
        assert row["kind"] == "section"
        assert row.get("parent_citation_path") is None and row.get("parent_id") is None
        assert metadata["self_contained_root"] is True
        assert metadata["detached_parent_citation_path"] == path.rsplit("/", 1)[0]
        assert row["source_as_of"] == row["expression_date"] == "2026-09-26"
        assert row["source_url"].startswith(
            "https://leginfo.legislature.ca.gov/faces/printCodeSectionWindow.xhtml?"
        )
        assert (
            f"&op_statues={op_statues}&op_chapter={op_chapter}&op_section={op_section}"
            in (row["source_url"])
        )
        siblings = [other for other in EXPECTED if other.split("--")[0] == path.split("--")[0]]
        assert metadata["variant_citation_paths"] == siblings
    coverage = json.loads((CORPUS_ROOT / f"coverage/us-ca/statute/{VERSION}.json").read_text())
    assert coverage["complete"] is True
    assert coverage["matched_count"] == coverage["source_count"] == len(EXPECTED)


def test_each_row_is_its_retained_leginfo_page() -> None:
    """Every row's version identity, slug and text come from its own retained page,
    and every retained file hashes to what the inventory and metadata record."""
    inventory = json.loads((CORPUS_ROOT / f"inventory/us-ca/statute/{VERSION}.json").read_text())
    items = {item["citation_path"]: item for item in inventory["items"]}
    for path, row in _rows().items():
        html = _source(row).read_bytes()
        assert hashlib.sha256(html).hexdigest() == items[path]["sha256"]
        detached = ("self_contained_root", "detached_parent_citation_path")
        assert items[path]["metadata"] == {
            key: value for key, value in row["metadata"].items() if key not in detached
        }
        version = leginfo_page_version(html)
        assert version is not None
        assert version.normalized() == EXPECTED[path][:3]
        soup = BeautifulSoup(html, "html.parser")
        history = _california_html_history(soup.find(id="single_law_section"))
        assert history == row["metadata"]["history"]
        assert leginfo_variant_slug(history, version) == row["metadata"]["variant"]
        assert row["body"] == _table_body(html)
        picker_meta = row["metadata"]["leginfo_picker"]
        picker_bytes = (CORPUS_ROOT / picker_meta["source_path"]).read_bytes()
        assert hashlib.sha256(picker_bytes).hexdigest() == picker_meta["sha256"]
        picker = parse_leginfo_picker(picker_bytes)
        assert picker is not None
        assert [
            (v["op_statues"], v["op_chapter"], v["op_section"], v["text"])
            for v in picker_meta["versions"]
        ] == [(*link.version.normalized(), link.text) for link in picker.links]
        assert picker.links[picker_meta["index"]].version.normalized() == EXPECTED[path][:3]
        fields = row["metadata"]["leginfo_retrieval"]["fields"]
        assert "javax.faces.ViewState" not in fields
        assert fields == picker.retrieval_fields(picker.links[picker_meta["index"]])
    retained = sorted(path.relative_to(SOURCES).as_posix() for path in SOURCES.rglob("*.html"))
    assert len(retained) == len(EXPECTED) + 4
    assert sum(name.startswith("california-leginfo-pickers/") for name in retained) == 4


def test_the_scope_rebuilds_offline_and_byte_identically_from_its_retained_bytes(
    tmp_path, monkeypatch
) -> None:
    """The retained pages and pickers are a complete download cache: rerunning the
    extraction command with the network blocked, then the parent detachment, gives
    the committed inventory, provisions, coverage and sources byte for byte."""
    import importlib.util

    cache = tmp_path / "cache"
    shutil.copytree(SOURCES, cache)

    class Offline:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}

        def get(self, *args, **kwargs):
            raise AssertionError("network used")

        post = get

    monkeypatch.setattr("axiom_corpus.corpus.states.requests.Session", Offline)
    base = tmp_path / "corpus"
    extract_california_code_sections(
        CorpusArtifactStore(base),
        version=PREFIX,
        sections=SPECS,
        source_as_of="2026-09-26",
        expression_date="2026-09-26",
        download_dir=cache,
        request_delay_seconds=0,
        preserve_tables=True,
    )
    spec = importlib.util.spec_from_file_location(
        "self_contain_usc_scope", REPO_ROOT / "scripts/self_contain_usc_scope.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.self_contain_scope(base, jurisdiction="us-ca", document_class="statute", version=VERSION)
    for relative in (
        f"inventory/us-ca/statute/{VERSION}.json",
        f"provisions/us-ca/statute/{VERSION}.jsonl",
        f"coverage/us-ca/statute/{VERSION}.json",
    ):
        assert (base / relative).read_bytes() == (CORPUS_ROOT / relative).read_bytes(), relative
    rebuilt = base / f"sources/us-ca/statute/{VERSION}"
    assert {
        path.relative_to(rebuilt).as_posix(): path.read_bytes() for path in rebuilt.rglob("*.html")
    } == {
        path.relative_to(SOURCES).as_posix(): path.read_bytes() for path in SOURCES.rglob("*.html")
    }


def test_every_us_ca_plain_row_of_these_sections_is_one_of_these_versions() -> None:
    """Differential check across carriers, over every us-ca statute scope: a plain-path row
    of a multi-version section is the same LegInfo version (op triple and sectionuid) as
    exactly one variant row here, with the same text apart from the history note."""
    rows = _rows()
    by_source_id = {row["source_id"]: path for path, row in rows.items()}
    seen: dict[str, set[str]] = {}
    for provisions in sorted((CORPUS_ROOT / "provisions/us-ca/statute").glob("*.jsonl")):
        for line in provisions.read_text().splitlines():
            plain_row = json.loads(line)
            plain = plain_row["citation_path"]
            if plain not in PLAIN_PATH_VERSIONS or plain_row.get("source_format") != (
                "california-leginfo-section-html"
            ):
                continue
            variant = PLAIN_PATH_VERSIONS[plain]
            assert by_source_id.get(plain_row["source_id"]) == variant, provisions.stem
            plain_html = _source(plain_row).read_bytes()
            assert leginfo_page_version(plain_html).normalized() == EXPECTED[variant][:3]
            old, new = _table_body(plain_html).splitlines(), rows[variant]["body"].splitlines()
            assert old[:-1] == new[:-1], (plain, provisions.stem)
            seen.setdefault(plain, set()).add(provisions.stem)
    assert seen == {
        "us-ca/statute/wic/11450": {CALWORKS_VERSION},
        "us-ca/statute/wic/11451.5": {CALWORKS_VERSION},
        "us-ca/statute/rtc/17552.3": {CHAPTER_VERSION},
        "us-ca/statute/rtc/17563.5": {CHAPTER_VERSION},
    }
    wic_old = _table_body(
        _source(
            [r for r in _jsonl(CALWORKS_VERSION) if r["citation_path"].endswith("/11450")][0]
        ).read_bytes()
    ).splitlines()[-1]
    wic_new = rows["us-ca/statute/wic/11450--operative-2021-07-01"]["body"].splitlines()[-1]
    assert wic_old.replace(
        "Sec. 2 of Stats. 2024, Ch. 798.", "Sec. 2 of Stats. 2026, Ch. 310."
    ) == (wic_new)


def test_wic_11450_versions_differ_only_where_leginfo_s_notes_say() -> None:
    rows = _rows()
    v1 = rows["us-ca/statute/wic/11450--operative-2021-07-01"]["body"].splitlines()
    v2 = rows["us-ca/statute/wic/11450--operative-2024-07-01"]["body"].splitlines()
    changed = [
        (tag, v1[i1][:12] if i1 < i2 else "", v2[j1][:12] if j1 < j2 else "")
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=v1, b=v2, autojunk=False).get_opcodes()
        if tag != "equal"
    ]
    assert changed == [
        ("replace", "(c) (1) The ", "(c) (1) The "),
        ("replace", "(e) In addit", "(e) In addit"),
        ("replace", "(B) A family", "(B) A family"),
        ("replace", "(iii) A fami", "(iii) A fami"),
        ("replace", "(n) This sec", "(n) This sec"),
    ]
    # (a)(1)(A) and its maximum-aid table read the same in both versions.
    table_end = next(i for i, line in enumerate(v1) if line.startswith("10 or more"))
    assert v1[: table_end + 1] == v2[: table_end + 1]
    assert v1[table_end].endswith("| 1,403")
    # AB 2765 (Stats. 2026, Ch. 310) raised the later version's recurring special needs
    # allowance in (e); the earlier version keeps ten dollars.
    (e1,) = [line for line in v1 if line.startswith("(e) ")]
    (e2,) = [line for line in v2 if line.startswith("(e) ")]
    assert "ten dollars ($10)" in e1 and "fifteen dollars ($15)" in e2
    assert e1.replace("ten dollars ($10)", "fifteen dollars ($15)") == e2
    assert "commencing October 1, 2023" in "\n".join(v1)
    assert "commencing October 1, 2023" not in "\n".join(v2)
    assert any(line.startswith("(p) ") for line in v1)
    assert not any(line.startswith(("(o) ", "(p) ")) for line in v2)


def test_the_double_jointed_r_and_tc_sections_differ_where_leginfo_prints_them() -> None:
    """Stats. 2002, Chs. 34 and 35 each added R&TC 17552.3 and 17563.5. LegInfo calls the
    Ch. 35 sections identical, but its 17563.5(b)(3) texts differ in one hyphenation."""
    rows = _rows()
    for section, differing in (("17552.3", []), ("17563.5", [4])):
        ch34, ch35 = (
            rows[path]["body"].splitlines()
            for path in EXPECTED
            if path.startswith(f"us-ca/statute/rtc/{section}--")
        )
        assert len(ch34) == len(ch35)
        lines = [i for i, (a, b) in enumerate(zip(ch34[:-1], ch35[:-1], strict=True)) if a != b]
        assert lines == differing, section
        assert "See identical section added by Stats. 2002, Ch. 35." in ch34[-1]
        assert "identical" not in ch35[-1]
    ch34_b3, ch35_b3 = (
        rows[path]["body"].splitlines()[4] for path in EXPECTED if "17563.5--" in path
    )
    assert ch34_b3.replace("three-taxable-year", "three taxable year") == ch35_b3


def test_no_other_us_ca_scope_carries_a_variant_path() -> None:
    carried: dict[str, str] = {}
    for path in sorted((CORPUS_ROOT / "provisions/us-ca").rglob("*.jsonl")):
        for line in path.read_text().splitlines():
            citation_path = json.loads(line)["citation_path"]
            if "--" in citation_path:
                carried[citation_path] = path.stem
    assert carried == dict.fromkeys(EXPECTED, VERSION)


@pytest.mark.parametrize(
    "cut",
    ["us-rulespec-2026-09-24-snap-fy2027-cola", "us-rulespec-2026-09-14-wave4-r2-union"],
)
def test_the_scope_joins_the_newest_cuts_us_ca_statute_scopes_cleanly(cut: str) -> None:
    """Additive: next to each line's us-ca statute scopes (CalWORKs plus the recovery scope,
    or CalWORKs plus the chapter scope) it shares no citation path and validates clean."""
    manifest = ReleaseManifest.load(REPO_ROOT / f"manifests/releases/{cut}.json")
    scopes = tuple(
        scope
        for scope in manifest.scopes
        if (scope.jurisdiction, scope.document_class) == ("us-ca", "statute")
    )
    release = ReleaseManifest(
        name=f"{cut}-us-ca-statute-with-concurrent-versions",
        quality_profile="complete-expression-dates-v1",
        scopes=(*scopes, ReleaseScope("us-ca", "statute", VERSION)),
    )
    report = validate_release(CORPUS_ROOT, release, strict_warnings=True, max_issues=50)
    assert report.to_mapping()["issue_count"] == 0, report.to_mapping()["issues"]
