"""Committed-artifact checks for the ``us-ca/statute/2026-07-13-recovery`` audit.

``scripts/audit_us_ca_statute_recovery_rows.py`` gives every row of the merged
recovery scope a verdict against its retained LegInfo page. The scope itself stays
unchanged. The run note records why no successor scope is built and how later
cuts supersede the scope.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from scripts.audit_us_ca_statute_recovery_rows import (
    DEFAULT_OUTPUT,
    LEGINFO_MENU,
    REFERENCE_CARRIERS,
    VERSION,
    audit,
    audit_page,
    classify_row,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data/corpus"
AUDIT = REPO_ROOT / DEFAULT_OUTPUT
RUN_NOTE = REPO_ROOT / "docs/ingest-runs/2026-09-25-us-ca-statute-recovery-audit.md"
RELEASES = REPO_ROOT / "manifests/releases"

WIC = (
    "2026-06-25-ca-wic-calworks-us-ca-sections-wic-11450-wic-11450.12-wic-11451.5-wic-11452-"
    "wic-11452.018"
)
PIT_CORE = (
    "2026-07-06-ca-rtc-pit-core-us-ca-sections-rtc-17041-rtc-17043-rtc-17045-rtc-17052-"
    "rtc-17054-rtc-17073.5"
)
CHAPTER = "2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7"
RTC_SECTIONS = (
    "17014",
    "17016",
    "17017",
    "17029",
    "17034",
    "17038",
    "17053.6",
    "17054.7",
    "17061",
    "17062.1",
)
WIC_ROOT = "us-ca/statute/wic/11450/a/1/A"
ROOTS = tuple(f"us-ca/statute/rtc/{section}" for section in RTC_SECTIONS) + (WIC_ROOT,)
CANADA_338 = "us-rulespec-2026-08-23-canada-338-suspension-union"
WAVE4 = ("us-rulespec-2026-09-14-wave4-union", "us-rulespec-2026-09-14-wave4-r2-union")


@cache
def _committed_audit() -> dict[str, Any]:
    return dict(json.loads(AUDIT.read_text(encoding="utf-8")))


@cache
def _recovery_rows() -> dict[str, dict[str, Any]]:
    path = CORPUS_ROOT / "provisions/us-ca/statute" / f"{VERSION}.jsonl"
    rows = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    return {row["citation_path"]: row for row in rows}


def _selector(name: str) -> dict[str, Any]:
    return dict(json.loads((RELEASES / f"{name}.json").read_text(encoding="utf-8")))


def _us_ca_statute_versions(selector: dict[str, Any]) -> list[str]:
    return [
        scope["version"]
        for scope in selector["scopes"]
        if (scope["jurisdiction"], scope["document_class"]) == ("us-ca", "statute")
    ]


def _validate(*versions: str) -> dict[str, Any]:
    release = ReleaseManifest(
        name="us-ca-2026-09-25-recovery-audit-validation",
        quality_profile="complete-expression-dates-v1",
        scopes=tuple(ReleaseScope("us-ca", "statute", version) for version in versions),
    )
    return dict(validate_release(CORPUS_ROOT, release, strict_warnings=True).to_mapping())


def test_committed_audit_matches_a_fresh_audit() -> None:
    assert audit(CORPUS_ROOT, REPO_ROOT) == _committed_audit()


def test_the_generic_document_extractor_reproduces_the_committed_scope() -> None:
    """The rows and inventory are what ``recover_ingest_batch._generic`` makes of each page.

    This replays history: ``_parse`` no longer routes these entries to ``_generic``,
    and the replay runs through the shared document-block extractor and lxml. If
    it fails after a change to that code, the committed scope has not changed;
    re-check the run note's "How the rows were made" section instead.
    """
    from scripts.recover_ingest_batch import _generic

    rows = list(_recovery_rows().values())
    items = json.loads(
        (CORPUS_ROOT / "inventory/us-ca/statute" / f"{VERSION}.json").read_text(encoding="utf-8")
    )["items"]
    replayed_rows: list[dict[str, Any]] = []
    replayed_items: list[dict[str, Any]] = []
    for root in (row for row in rows if row["kind"] == "document"):
        document_id = root["source_id"]
        provenance = json.loads(
            (
                CORPUS_ROOT
                / "sources/us-ca/statute"
                / VERSION
                / "provenance"
                / f"{document_id}.json"
            ).read_text(encoding="utf-8")
        )
        entry = {
            "document_id": document_id,
            "jurisdiction": "us-ca",
            "document_class": "statute",
            "parser": root["metadata"]["recovery_parser"],
            "covers_citation_paths": [root["citation_path"]],
            "proposed_version": VERSION,
        }
        new_items, records = _generic(
            entry,
            Path(document_id),
            (CORPUS_ROOT / root["source_path"]).read_bytes(),
            provenance,
            root["source_path"],
        )
        replayed_rows.extend(record.to_mapping() for record in records)
        replayed_items.extend(item.to_mapping() for item in new_items)
    message = "the shared extractor no longer reproduces the merged scope; see the docstring"
    assert replayed_rows == rows, message
    assert replayed_items == items, message


def test_only_the_rtc_block_2_rows_carry_section_text() -> None:
    by_verdict: dict[str, list[str]] = {}
    for row in _committed_audit()["rows"]:
        by_verdict.setdefault(row["verdict"], []).append(row["citation_path"])
    assert sorted(by_verdict) == [
        "empty_document_root",
        "leginfo_page_chrome",
        "picker_history_notes_only",
        "section_text_without_history",
    ]
    assert sorted(by_verdict["empty_document_root"]) == sorted(ROOTS)
    assert sorted(by_verdict["leginfo_page_chrome"]) == sorted(f"{root}/block-1" for root in ROOTS)
    assert by_verdict["picker_history_notes_only"] == [f"{WIC_ROOT}/block-2"]
    assert sorted(by_verdict["section_text_without_history"]) == sorted(
        f"us-ca/statute/rtc/{section}/block-2" for section in RTC_SECTIONS
    )
    assert _committed_audit()["summary"]["rows_without_section_text"] == 23


def test_retained_pages_are_the_signed_bytes_and_the_wic_page_is_a_version_picker() -> None:
    files = _committed_audit()["files"]
    assert len(files) == 11
    assert all(f["sha256_matches_provenance"] for f in files)
    assert all(f["sha256_matches_signed_manifest"] for f in files)
    sections = {f["section_path"] for f in files if f["page_type"] == "single_law_section"}
    assert sections == {f"us-ca/statute/rtc/{section}" for section in RTC_SECTIONS}
    [wic] = [f for f in files if f["page_type"] == "select_from_multiples"]
    assert (wic["document_id"], wic["section_path"]) == (
        "us-ca-code-wic",
        "us-ca/statute/wic/11450",
    )
    assert wic["recovery_citation_path"] == WIC_ROOT
    assert [
        (v["op_statues"], v["op_chapter"], v["op_section"]) for v in wic["picker_versions"]
    ] == [("2024", "798", "1"), ("2024", "798", "2")]


def test_the_wic_rows_hold_chrome_and_picker_notes_verbatim() -> None:
    rows = _recovery_rows()
    assert not rows[WIC_ROOT]["body"]
    assert rows[WIC_ROOT]["citation_label"] == rows[WIC_ROOT]["heading"] == "us ca code wic"
    chrome = rows[f"{WIC_ROOT}/block-1"]["body"].split("\n\n")
    assert chrome == [
        *LEGINFO_MENU,
        "California Law >>",
        ">>",
        "Welfare and Institutions Code - WIC",
    ]
    assert rows[f"{WIC_ROOT}/block-2"]["body"] == (
        "(Amended (as amended by Stats. 2022, Ch. 715, Sec. 2) by Stats. 2024, Ch. 798, Sec. 1.) "
        "(Amended (as added by Stats. 2022, Ch. 715, Sec. 3) by Stats. 2024, Ch. 798, Sec. 2.)"
    )


def _page(document_id: str) -> dict[str, Any]:
    path = CORPUS_ROOT / "sources/us-ca/statute" / VERSION / "official-documents" / document_id
    return audit_page(path.read_bytes())


def _drop_first_paragraph(body: str) -> str:
    return body.split("\n\n", 1)[1]


def _rename_breadcrumb(body: str) -> str:
    return body.replace("Code Section", "Welfare and Institutions Code - WIC")


def _swap_notes(body: str) -> str:
    first, second = body.split(") (", 1)
    return f"({second} {first})"


def _truncate(body: str) -> str:
    return body[: len(body) // 2]


@pytest.mark.parametrize(
    ("document_id", "citation_path", "mutate"),
    [
        ("us-ca-code-rtc", "us-ca/statute/rtc/17014/block-2", _drop_first_paragraph),
        ("us-ca-code-rtc", "us-ca/statute/rtc/17014/block-1", _rename_breadcrumb),
        ("us-ca-code-rtc", "us-ca/statute/rtc/17014/block-1", _truncate),
        ("us-ca-code-wic", f"{WIC_ROOT}/block-2", _swap_notes),
        ("us-ca-code-wic", f"{WIC_ROOT}/block-2", _truncate),
    ],
    ids=[
        "text-missing-paragraph",
        "chrome-wrong-breadcrumb",
        "chrome-truncated",
        "picker-notes-swapped",
        "picker-notes-truncated",
    ],
)
def test_classifier_refuses_altered_rows(document_id: str, citation_path: str, mutate: Any) -> None:
    page = _page(document_id)
    row = dict(_recovery_rows()[citation_path])
    assert classify_row(row, page) != "unclassified"
    row["body"] = mutate(row["body"])
    assert classify_row(row, page) == "unclassified"


def test_the_chapter_scope_carries_each_rtc_section_with_the_retained_text() -> None:
    assert REFERENCE_CARRIERS == (WIC, CHAPTER)
    carriage = {entry["section_path"]: entry for entry in _committed_audit()["carriage"]}
    for section in RTC_SECTIONS:
        [carrier] = carriage[f"us-ca/statute/rtc/{section}"]["carriers"]
        assert (carrier["version"], carrier["kind"]) == (CHAPTER, "section")
        assert carrier["source_as_of"] == "2026-09-14"
        assert carrier["body_equals_recovery_page_text"] is True


def test_the_calworks_scope_carries_the_first_offered_wic_11450_version() -> None:
    carriage = {entry["section_path"]: entry for entry in _committed_audit()["carriage"]}
    [carrier] = carriage["us-ca/statute/wic/11450"]["carriers"]
    assert (carrier["version"], carrier["kind"]) == (WIC, "section")
    assert carrier["picker_version_carried"] == [0]
    assert carrier["history"].endswith(
        "See later operative version, as amended by Sec. 2 of Stats. 2024, Ch. 798.)"
    )


def test_the_recovery_scope_cannot_join_a_release_with_the_chapter_scope() -> None:
    report = _validate(VERSION, CHAPTER)
    duplicates = sorted(
        issue["message"].split()[1]
        for issue in report["issues"]
        if issue["code"] == "duplicate_release_citation"
    )
    assert duplicates == [f"us-ca/statute/rtc/{section}" for section in sorted(RTC_SECTIONS)]


def test_release_validation_does_not_see_the_defects() -> None:
    """The gate passes the scope; only this audit and the run note record the defects.

    The run note's follow-up 3 proposes a gate check for these rows. When it lands,
    this test is expected to fail: replace it, and update the note's "The release
    gate does not catch these rows" bullet.
    """
    report = _validate(VERSION)
    assert (report["ok"], report["issue_count"]) == (True, 0)


def test_the_newest_tracked_cuts_already_swap_the_recovery_scope_for_the_chapter() -> None:
    for name in WAVE4:
        versions = _us_ca_statute_versions(_selector(name))
        assert VERSION not in versions
        assert PIT_CORE not in versions
        assert {WIC, CHAPTER} <= set(versions)


def test_the_same_swap_validates_on_the_canada_338_line() -> None:
    versions = _us_ca_statute_versions(_selector(CANADA_338))
    assert {VERSION, PIT_CORE, WIC} <= set(versions)
    assert CHAPTER not in versions
    swapped = sorted([v for v in versions if v not in (VERSION, PIT_CORE)] + [CHAPTER])
    report = _validate(*swapped)
    assert (report["ok"], report["issue_count"]) == (True, 0)


# Tracked selectors cut before this audit that select the recovery scope (as of
# main b5b637167). They are immutable, so they keep it. No later selector may add
# it back.
SELECTORS_WITH_RECOVERY = frozenset(
    {
        "us-rulespec-2026-07-13",
        "us-rulespec-2026-07-16",
        "us-rulespec-2026-07-17",
        "us-rulespec-2026-07-17-pit-recovery",
        "us-rulespec-2026-07-18",
        "us-rulespec-2026-07-19",
        "us-rulespec-2026-07-19-dedup",
        "us-rulespec-2026-07-21-az-140es-current",
        "us-rulespec-2026-07-21-ga-pit-current",
        "us-rulespec-2026-07-21-ks-k40es-current",
        "us-rulespec-2026-07-21-mi-pit-current",
        "us-rulespec-2026-07-21-oh-hb96-current",
        "us-rulespec-2026-07-21-pa-pit-current",
        "us-rulespec-2026-07-22-current",
        "us-rulespec-2026-07-22-current-la-status-fix",
        "us-rulespec-2026-07-22-hi-capital-gain-current",
        "us-rulespec-2026-07-24-cms-435-correction",
        "us-rulespec-2026-07-24-cms-435-correction-immutable-scopes",
        "us-rulespec-2026-07-24-sc-act110-current",
        "us-rulespec-2026-07-24-snap-cms-pit-union",
        "us-rulespec-2026-07-31-idaho-statutes-current",
        "us-rulespec-2026-08-03-ecps-pit-tariff-union",
        "us-rulespec-2026-08-08-obbb-alien-snap",
        "us-rulespec-2026-08-09-cutover-surface-union",
        "us-rulespec-2026-08-23-canada-338-suspension-union",
        "us-rulespec-2026-09-11-program-ingestion-union",
        "us-rulespec-2026-09-13-cms-state-plans-union",
        "us-rulespec-2026-09-13-federal-and-plans-union",
        "us-rulespec-2026-09-13-followup-union",
        "us-rulespec-2026-09-24-snap-fy2027-cola",
        "us-rulespec-ny-snap-2026-07-17",
        "us-rulespec-snap-2026-07-21",
    }
)


def test_no_new_tracked_selector_selects_the_recovery_scope() -> None:
    """A new cut swaps the recovery scope (and PIT core) for the chapter scope.

    See "How later cuts supersede the scope" in the run note.
    """
    selecting = {
        path.stem
        for path in RELEASES.glob("*.json")
        if VERSION in _us_ca_statute_versions(_selector(path.stem))
    }
    assert selecting - SELECTORS_WITH_RECOVERY == set(), (
        f"{sorted(selecting - SELECTORS_WITH_RECOVERY)} select us-ca/statute/{VERSION}; "
        f"replace it and {PIT_CORE} with {CHAPTER} (or its successor), as {RUN_NOTE.name} "
        "describes"
    )
    assert selecting >= SELECTORS_WITH_RECOVERY


def test_run_note_names_the_audit_command() -> None:
    command = (
        "uv run --extra dev python scripts/audit_us_ca_statute_recovery_rows.py "
        "--base data/corpus --output docs/ingest-runs/2026-09-25-us-ca-statute-recovery-audit.json"
    )
    assert f"```bash\n{command}\n```" in RUN_NOTE.read_text(encoding="utf-8")
