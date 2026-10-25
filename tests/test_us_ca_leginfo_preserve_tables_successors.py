"""Committed-artifact checks for the table-preserving California LegInfo successors.

Each successor re-extracts one merged ``california-code-sections`` scope from its
retained LegInfo bytes with ``--preserve-tables``
(``scripts/repro/us_ca_leginfo_preserve_tables_successors.py``). The originals
stay unchanged; the draft selector swaps the two that the newest US cut selects.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from functools import cache
from pathlib import Path
from typing import Any, NoReturn

import pytest
import requests

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.corpus.supabase import deterministic_provision_id
from scripts.repro.us_ca_leginfo_preserve_tables_successors import (
    REPRO_COMMAND,
    REVISION,
    SUCCESSORS,
    Successor,
    _detach_parents,
    build_successor,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data/corpus"
PREDECESSOR_SELECTOR = REPO_ROOT / "manifests/releases/us-rulespec-2026-09-14-wave4-r2-union.json"
DRAFT_SELECTOR = REPO_ROOT / "docs/ingest-runs/2026-09-24-ca-leginfo-preserve-tables.selector.json"
RUN_NOTE = REPO_ROOT / "docs/ingest-runs/2026-09-24-ca-leginfo-preserve-tables-successors.md"
AUDIT = REPO_ROOT / "docs/ingest-runs/2026-09-24-ca-leginfo-preserve-tables-audit.json"
LITERAL_REPRO_COMMAND = (
    "uv run --extra dev python "
    "scripts/repro/us_ca_leginfo_preserve_tables_successors.py --base data/corpus"
)

WIC = "2026-06-25-ca-wic-calworks-us-ca-sections-wic-11450-wic-11450.12-wic-11451.5-wic-11452-wic-11452.018"
PIT_CORE = (
    "2026-07-06-ca-rtc-pit-core-us-ca-sections-rtc-17041-rtc-17043-rtc-17045-rtc-17052-"
    "rtc-17054-rtc-17073.5"
)
CHAPTER = "2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7"
SB_1435 = "2026-09-23-ca-rtc-sb-1435-us-ca-sections-rtc-17024.5-rtc-17052"
SSI_SSP = "2026-06-27-ca-ssi-ssp-wic-12200-us-ca-sections-wic-12200"
BBCE = "2026-07-28-ca-cdss-calfresh-bbce-authority-us-ca-sections-wic-18901.3-wic-18901.5"

SUCCESSOR = {
    original: f"{original}-r2026-09-24-preserve-tables" for original in (WIC, PIT_CORE, CHAPTER)
}
CAPTURE_DATE = {WIC: "2026-06-25", PIT_CORE: "2026-07-06", CHAPTER: "2026-09-14"}
SECTION_COUNT = {WIC: 5, PIT_CORE: 6, CHAPTER: 1029}
SELF_CONTAINED = {WIC: False, PIT_CORE: False, CHAPTER: True}
CHANGED_BODIES = {
    WIC: {"wic/11450", "wic/11452"},
    PIT_CORE: {"rtc/17041", "rtc/17052"},
    CHAPTER: {
        "rtc/17024.5",
        "rtc/17041",
        "rtc/17052",
        "rtc/17052.6",
        "rtc/17053.5",
        "rtc/17053.73",
        "rtc/17276",
        "rtc/17955",
        "rtc/18628",
        "rtc/18648",
        "rtc/18662",
        "rtc/19025",
        "rtc/19141.5",
        "rtc/19183",
    },
}
_WORD = re.compile(r"\S+")


def _scope_file(kind: str, version: str) -> Path:
    suffix = ".jsonl" if kind == "provisions" else ".json"
    return CORPUS_ROOT / kind / "us-ca/statute" / f"{version}{suffix}"


@cache
def _records(version: str) -> tuple[dict[str, Any], ...]:
    lines = _scope_file("provisions", version).read_text().splitlines()
    return tuple(json.loads(line) for line in lines)


@cache
def _inventory(version: str) -> tuple[dict[str, Any], ...]:
    return tuple(json.loads(_scope_file("inventory", version).read_text())["items"])


def _words(text: str | None) -> Counter[str]:
    return Counter(word for word in _WORD.findall(text or "") if word != "|")


@cache
def _reextract(source_path: str) -> tuple[str | None, Counter[str]]:
    """Return the table-preserving body and the page's visible words, less the h6."""
    from bs4 import BeautifulSoup

    from axiom_corpus.corpus.states import (
        _california_html_current_section_div,
        _california_html_section_body,
    )

    soup = BeautifulSoup((CORPUS_ROOT / source_path).read_bytes(), "html.parser")
    root = soup.find(id="single_law_section") or soup
    body = _california_html_section_body(root, preserve_tables=True)
    visible = copy.copy(_california_html_current_section_div(root) or root)
    for heading in visible.find_all("h6"):
        heading.decompose()
    return body, _words(visible.get_text(" ", strip=True))


def _body_lines(version: str, citation: str) -> list[str]:
    [record] = [r for r in _records(version) if r["citation_path"] == f"us-ca/statute/{citation}"]
    return str(record["body"]).splitlines()


@pytest.mark.parametrize("original", sorted(SUCCESSOR))
def test_successor_rows_differ_from_the_original_only_in_version_path_and_body(
    original: str,
) -> None:
    successor = SUCCESSOR[original]
    old_rows, new_rows = _records(original), _records(successor)
    assert [r["citation_path"] for r in new_rows] == [r["citation_path"] for r in old_rows]
    changed = set()
    for old, new in zip(old_rows, new_rows, strict=True):
        assert new["version"] == successor
        assert new["source_path"] == old["source_path"].replace(original, successor)
        assert new["source_as_of"] == new["expression_date"] == CAPTURE_DATE[original]
        if new["body"] != old["body"]:
            changed.add(new["citation_path"].removeprefix("us-ca/statute/"))
        rest = {"version", "source_path", "body"}
        assert {k: v for k, v in new.items() if k not in rest} == {
            k: v for k, v in old.items() if k not in rest
        }
        # Nothing the original body carried is lost.
        assert not _words(old["body"]) - _words(new["body"])
    assert changed == CHANGED_BODIES[original]


_CHUNK = 150
_BODY_CHUNKS = [
    (original, start)
    for original, count in SECTION_COUNT.items()
    for start in range(0, count, _CHUNK)
]


@pytest.mark.parametrize(("original", "start"), _BODY_CHUNKS)
def test_successor_bodies_are_table_preserving_and_hold_exactly_the_visible_text(
    original: str, start: int
) -> None:
    records = _records(SUCCESSOR[original])
    assert len(records) == SECTION_COUNT[original]
    for record in records[start : start + _CHUNK]:
        body, visible = _reextract(record["source_path"])
        assert record["body"] == body
        # Independent of the extractor: every word a reader sees in the section,
        # and no word the page does not repeat, appears in the body.
        assert _words(record["body"]) == visible, record["citation_path"]


@pytest.mark.parametrize("original", sorted(SUCCESSOR))
def test_successor_sources_are_the_retained_leginfo_bytes(original: str) -> None:
    successor = SUCCESSOR[original]
    old_items, new_items = _inventory(original), _inventory(successor)
    assert len(new_items) == len(old_items)
    for old, new in zip(old_items, new_items, strict=True):
        assert new["source_path"] == old["source_path"].replace(original, successor)
        assert {k: v for k, v in new.items() if k != "source_path"} == {
            k: v for k, v in old.items() if k != "source_path"
        }
        payload = (CORPUS_ROOT / new["source_path"]).read_bytes()
        assert payload == (CORPUS_ROOT / old["source_path"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == new["sha256"]
    source_root = CORPUS_ROOT / "sources/us-ca/statute" / successor
    assert len([p for p in source_root.rglob("*") if p.is_file()]) == len(new_items)


@pytest.mark.parametrize("original", sorted(SUCCESSOR))
def test_successor_coverage_is_complete_and_parents_are_detached_as_before(
    original: str,
) -> None:
    successor = SUCCESSOR[original]
    coverage = json.loads(_scope_file("coverage", successor).read_text())
    old_coverage = json.loads(_scope_file("coverage", original).read_text())
    assert coverage == {**old_coverage, "version": successor}
    assert coverage["complete"] is True
    for record in _records(successor):
        assert record.get("parent_citation_path") is None
        assert record.get("parent_id") is None
        assert ("self_contained_root" in record["metadata"]) is SELF_CONTAINED[original]


def test_successors_keep_repeated_table_cells_row_labels_and_paragraphs() -> None:
    eitc = _body_lines(SUCCESSOR[CHAPTER], "rtc/17052")
    for row in (
        "No qualifying children | 7.65% | 7.65%",
        "No qualifying children | $3,290 | $3,290",
        "2 or more qualifying children | $6,935 | $6,935",
        "No qualifying children | 2.20% | 1.22%",
        "3 or more qualifying children | $14,302 | $14,302",
    ):
        assert eitc.count(row) == 1
    # The (m)-(o) tables sit inside a <p>; the wrapper adds no flattened copy.
    assert not [
        line for line in eitc if line.startswith("In the case of an eligible individual with: The")
    ]

    rates = _body_lines(SUCCESSOR[CHAPTER], "rtc/17041")
    assert rates.count("If the taxable income is: | The tax is:") == 2
    assert "Not over $7,300 ........................ | 1% of the taxable income" in rates

    renters = _body_lines(SUCCESSOR[CHAPTER], "rtc/17053.5")
    for clause in (
        "(I) Two hundred fifty dollars ($250) if the qualified renter has no dependents, "
        "as defined in Section 17056.",
        "(II) Five hundred dollars ($500) if the qualified renter has one or more "
        "dependents, as defined in Section 17056.",
    ):
        assert renters.count(clause) == 2
        assert _body_lines(CHAPTER, "rtc/17053.5").count(clause) == 1

    shelter = _body_lines(SUCCESSOR[CHAPTER], "rtc/18628")
    assert shelter.count("(1) Sixty days after entering into the transaction.") == 2

    aid = _body_lines(SUCCESSOR[WIC], "wic/11450")
    assert "10 or more ........................ | 1,403" in aid
    assert len([line for line in aid if line.startswith("(ib) Beginning January 1, 2026")]) == 2

    installments = _body_lines(SUCCESSOR[CHAPTER], "rtc/19025")
    assert (
        "After the last day of the 8th month and before the 1st day of the 12th month of the "
        "taxable year ........................ | __ | __ | __ | 100"
    ) in installments


def test_draft_selector_swaps_exactly_the_two_selected_originals() -> None:
    predecessor = json.loads(PREDECESSOR_SELECTOR.read_text())
    draft = json.loads(DRAFT_SELECTOR.read_text())
    assert draft["name"] == "us-rulespec-2026-09-24-ca-preserve-tables"
    assert draft["quality_profile"] == predecessor["quality_profile"]
    swapped = {
        (scope["jurisdiction"], scope["document_class"], scope["version"])
        for scope in predecessor["scopes"]
        if scope["version"] in SUCCESSOR
    }
    assert swapped == {("us-ca", "statute", WIC), ("us-ca", "statute", CHAPTER)}
    expected = [
        {**scope, "version": SUCCESSOR.get(scope["version"], scope["version"])}
        for scope in predecessor["scopes"]
    ]
    assert draft["scopes"] == expected
    keys = [(s["jurisdiction"], s["document_class"], s["version"]) for s in draft["scopes"]]
    assert keys == sorted(keys)


def _us_ca_statute_release(*versions: str) -> dict[str, Any]:
    release = ReleaseManifest(
        name="us-ca-2026-09-24-preserve-tables-validation",
        quality_profile="complete-expression-dates-v1",
        scopes=tuple(ReleaseScope("us-ca", "statute", version) for version in versions),
    )
    report = validate_release(CORPUS_ROOT, release, strict_warnings=True, max_issues=50)
    return dict(report.to_mapping())


def test_draft_selector_us_ca_statute_scopes_pass_release_validation() -> None:
    draft = json.loads(DRAFT_SELECTOR.read_text())
    versions = [
        scope["version"]
        for scope in draft["scopes"]
        if (scope["jurisdiction"], scope["document_class"]) == ("us-ca", "statute")
    ]
    assert versions == [SUCCESSOR[WIC], SSI_SSP, BBCE, SUCCESSOR[CHAPTER]]
    report = _us_ca_statute_release(*versions)
    assert report["ok"] is True
    assert report["issue_count"] == 0


@pytest.mark.parametrize(
    ("other", "shared"),
    [
        (SUCCESSOR[PIT_CORE], ("17041", "17043", "17045", "17052", "17054", "17073.5")),
        (SB_1435, ("17024.5", "17052")),
    ],
)
def test_scopes_that_repeat_chapter_sections_cannot_join_its_release(
    other: str, shared: tuple[str, ...]
) -> None:
    report = _us_ca_statute_release(SUCCESSOR[CHAPTER], other)
    issues = report["issues"]
    assert sorted((issue["code"], issue["message"].split()[1]) for issue in issues) == [
        ("duplicate_release_citation", f"us-ca/statute/rtc/{section}") for section in shared
    ]


def test_repro_script_names_the_same_successors() -> None:
    assert REVISION == "r2026-09-24-preserve-tables"
    assert {s.original_version: s.version for s in SUCCESSORS} == SUCCESSOR
    assert REPRO_COMMAND == LITERAL_REPRO_COMMAND
    assert f"```bash\n{LITERAL_REPRO_COMMAND}\n```" in RUN_NOTE.read_text(encoding="utf-8")


def test_successor_versions_sort_after_their_originals_for_the_release_gate() -> None:
    """check_release_gate's scope_monotonicity orders versions by (date, string)."""
    from scripts.check_release_gate import _version_key

    for original, successor in SUCCESSOR.items():
        assert _version_key(successor) > _version_key(original)


@pytest.mark.parametrize(
    "successor", [s for s in SUCCESSORS if s.original_version in (WIC, PIT_CORE)]
)
def test_offline_rebuild_is_byte_identical(
    successor: Successor, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The chapter successor is covered by the chunked checks above; a full rebuild
    of its 1,029 pages is too slow for one test."""

    def fail_network(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("offline successor rebuild attempted network access")

    monkeypatch.setattr(requests.sessions.Session, "request", fail_network)
    report = build_successor(tmp_path, CORPUS_ROOT, successor)
    version = successor.version
    rebuilt = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*") if p.is_file())
    source_root = CORPUS_ROOT / "sources/us-ca/statute" / version
    committed = [p.relative_to(CORPUS_ROOT) for p in source_root.rglob("*") if p.is_file()]
    committed += [
        _scope_file(kind, version).relative_to(CORPUS_ROOT)
        for kind in ("inventory", "provisions", "coverage")
    ]
    assert report["files"] == len(rebuilt)
    assert rebuilt == sorted(committed)
    for relative in rebuilt:
        assert (tmp_path / relative).read_bytes() == (CORPUS_ROOT / relative).read_bytes()


@cache
def _committed_audit() -> dict[str, dict[str, Any]]:
    return {scope["version"]: scope for scope in json.loads(AUDIT.read_text())["scopes"]}


def test_committed_audit_records_the_loss_and_its_repair() -> None:
    scopes = _committed_audit()
    assert set(scopes) == {WIC, SSI_SSP, PIT_CORE, BBCE, CHAPTER, SB_1435, *SUCCESSOR.values()}
    missing = {WIC: 138, PIT_CORE: 69, CHAPTER: 385}
    for original, successor in SUCCESSOR.items():
        details = scopes[original]["section_details"]
        changed = {
            path.removeprefix("us-ca/statute/")
            for path, entry in details.items()
            if entry["changed_by_preserve_tables"]
        }
        assert changed == CHANGED_BODIES[original]
        assert scopes[original]["default_missing_words"] == missing[original]
        sections = SECTION_COUNT[original]
        assert scopes[original]["sections"] == scopes[successor]["sections"] == sections
        assert scopes[original]["committed_modes"] == {
            "default": len(changed),
            "either": sections - len(changed),
        }
        assert scopes[successor]["committed_modes"] == {
            "either": sections - len(changed),
            "preserve-tables": len(changed),
        }
    assert scopes[SSI_SSP]["committed_modes"] == {"either": 1}
    assert scopes[BBCE]["committed_modes"] == {"either": 2}
    assert scopes[SB_1435]["committed_modes"] == {"preserve-tables": 2}
    for scope in scopes.values():
        assert scope["preserve_tables_missing_words"] == 0
        assert scope["preserve_tables_extra_words"] == 0


@pytest.mark.parametrize(
    "version", [WIC, SSI_SSP, PIT_CORE, BBCE, CHAPTER, SB_1435, *SUCCESSOR.values()]
)
def test_committed_audit_matches_a_fresh_audit(version: str) -> None:
    from scripts.audit_california_leginfo_table_loss import audit_scope

    assert (
        audit_scope(CORPUS_ROOT, _scope_file("provisions", version))
        == (_committed_audit()[version])
    )


@pytest.mark.parametrize("successor", SUCCESSORS, ids=lambda s: s.original_version[:30])
def test_parent_detachment_replays_onto_the_committed_rows(
    successor: Successor, tmp_path: Path
) -> None:
    """Undo the detachment on the committed rows, stage them under the original
    version as the adapter emits them, and replay the repro's detachment step."""
    original, version = successor.original_version, successor.version
    old_key = f"sources/us-ca/statute/{original}/"
    new_key = f"sources/us-ca/statute/{version}/"
    staged: list[ProvisionRecord] = []
    for row in _records(version):
        metadata = {
            k: v
            for k, v in row["metadata"].items()
            if k not in {"self_contained_root", "detached_parent_citation_path"}
        }
        parent = metadata["parent_citation_path"]
        staged.append(
            ProvisionRecord.from_mapping(
                {
                    **row,
                    "version": original,
                    "source_path": row["source_path"].replace(new_key, old_key),
                    "parent_citation_path": parent,
                    "parent_id": deterministic_provision_id(parent),
                    "metadata": metadata,
                }
            )
        )
    items = [
        SourceInventoryItem.from_mapping(
            {**item, "source_path": item["source_path"].replace(new_key, old_key)}
        )
        for item in _inventory(version)
    ]
    store = CorpusArtifactStore(tmp_path)
    store.write_inventory(store.inventory_path("us-ca", "statute", original), items)
    store.write_provisions(store.provisions_path("us-ca", "statute", original), staged)

    _detach_parents(tmp_path, successor)

    replayed = load_provisions(store.provisions_path("us-ca", "statute", original))
    assert [
        {
            **record.to_mapping(),
            "version": version,
            "source_path": (record.source_path or "").replace(old_key, new_key),
        }
        for record in replayed
    ] == list(_records(version))
