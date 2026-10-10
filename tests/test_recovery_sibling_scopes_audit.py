"""Committed-artifact checks for the audit of the July 2026 recovery sibling scopes.

``scripts/audit_recovery_sibling_scopes.py`` gives every row of the 18 scopes a
verdict against its retained source file, and
``scripts/resolve_recovery_sibling_citations.py`` records what rulespec-us
citations resolve to. The scopes themselves stay unchanged; the run note
(``docs/ingest-runs/2026-09-27-recovery-sibling-scopes-audit.md``) records the
successor decisions and the swap for each later cut.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from scripts.audit_recovery_sibling_scopes import (
    DEFAULT_OUTPUT,
    NO_TEXT_VERDICTS,
    SCOPES,
    audit_scope,
    classify_row,
    load_sources,
    read_page,
    selectors_selecting,
)
from scripts.resolve_recovery_sibling_citations import (
    DEFAULT_OUTPUT as DOWNSTREAM_OUTPUT,
)
from scripts.resolve_recovery_sibling_citations import SWAPS

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data/corpus"
AUDIT = REPO_ROOT / DEFAULT_OUTPUT
DOWNSTREAM = REPO_ROOT / DOWNSTREAM_OUTPUT
RUN_NOTE = REPO_ROOT / "docs/ingest-runs/2026-09-27-recovery-sibling-scopes-audit.md"
RELEASES = REPO_ROOT / "manifests/releases"
BY_KEY = {scope.key: scope for scope in SCOPES}
OBBB = "us-rulespec-2026-08-08-obbb-alien-snap"
WAVE4_R2 = "us-rulespec-2026-09-14-wave4-r2-union"


@cache
def _audit() -> dict[str, Any]:
    return dict(json.loads(AUDIT.read_text(encoding="utf-8")))


@cache
def _downstream() -> dict[str, Any]:
    return dict(json.loads(DOWNSTREAM.read_text(encoding="utf-8")))


def _scope_audit(key: str) -> dict[str, Any]:
    return dict(_audit()["scopes"][key])


def _rows(key: str) -> dict[str, dict[str, Any]]:
    path = CORPUS_ROOT / "provisions" / f"{key}.jsonl"
    rows = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
    return {row["citation_path"]: row for row in rows}


def _verdicts(key: str) -> dict[str, str]:
    return {row["citation_path"]: row["verdict"] for row in _scope_audit(key)["rows"]}


def _selector_versions(name: str, jurisdiction: str, document_class: str) -> list[str]:
    payload = json.loads((RELEASES / f"{name}.json").read_text(encoding="utf-8"))
    return [
        scope["version"]
        for scope in payload["scopes"]
        if (scope["jurisdiction"], scope["document_class"]) == (jurisdiction, document_class)
    ]


def _validate(jurisdiction: str, document_class: str, *versions: str) -> dict[str, Any]:
    release = ReleaseManifest(
        name="recovery-sibling-audit-validation",
        quality_profile="complete-expression-dates-v1",
        scopes=tuple(ReleaseScope(jurisdiction, document_class, v) for v in versions),
    )
    return dict(validate_release(CORPUS_ROOT, release, strict_warnings=True).to_mapping())


@pytest.mark.parametrize("key", [scope.key for scope in SCOPES])
def test_committed_audit_matches_a_fresh_audit(key: str) -> None:
    """Everything but selector membership, which later cuts may extend."""
    fresh = audit_scope(CORPUS_ROOT, REPO_ROOT, BY_KEY[key])
    committed = _scope_audit(key)
    assert {k: v for k, v in fresh.items() if k != "selectors"} == {
        k: v for k, v in committed.items() if k != "selectors"
    }


@pytest.mark.parametrize("key", [scope.key for scope in SCOPES])
def test_recorded_selector_membership_still_holds(key: str) -> None:
    """Tracked selectors are immutable: the recorded ones still select the scope.

    A new selector that selects it is allowed; this is not a freeze guard.
    """
    recorded = _scope_audit(key)["selectors"]
    current = set(selectors_selecting(REPO_ROOT, BY_KEY[key]))
    assert set(recorded["names"]) <= current
    assert recorded["count"] == len(recorded["names"])
    assert recorded["key_lines"] == {name: name in current for name in recorded["key_lines"]}


def test_every_row_is_classified_and_counted() -> None:
    total = 0
    for key, scope in _audit()["scopes"].items():
        assert "unclassified" not in scope["summary"]["verdicts"], key
        assert sum(scope["summary"]["verdicts"].values()) == scope["summary"]["rows"]
        assert scope["summary"]["rows"] == len(_rows(key))
        total += scope["summary"]["rows"]
    assert total == 756


def test_retained_files_are_the_signed_bytes() -> None:
    for key, scope in _audit()["scopes"].items():
        for record in scope["files"]:
            assert record["sha256_matches_signed_manifest"] is True, (key, record["document_id"])
            # Only the adapter-made Colorado Works PDF, consolidated in from another
            # scope, has no provenance sidecar.
            expected = (
                None if record["document_id"] == "us-co-ccr-9-2503-6-colorado-works" else True
            )
            assert record["sha256_matches_provenance"] is expected, (key, record["document_id"])


def test_rows_are_what_the_recovery_builders_make_of_the_retained_bytes() -> None:
    """Replay the July builders on every page whose rows they still reproduce.

    This replays history through ``scripts/recover_ingest_batch.py`` and the shared
    extractor. If it fails after a change to that code, the committed scopes have
    not changed; re-check the run note's "How the rows were made" section.
    """
    from scripts.recover_ingest_batch import _generic, _targeted_state_html

    replayed = 0
    for key in (
        "us-ny/statute/2026-07-13-recovery",
        "us-id/statute/2026-07-13-recovery",
        "us-me/statute/2026-07-13-recovery",
        "us-mn/statute/2026-07-13-recovery",
        "us-ut/statute/2026-07-13-recovery",
        "us-sc/statute/2026-07-13-recovery",
        "us-mt/regulation/2026-07-13-recovery",
        "us-fl/regulation/2026-07-13-recovery",
        "us-sc/regulation/2026-07-13-recovery",
        "us-tn/regulation/2026-07-13-recovery",
        "us-in/manual/2026-07-13-recovery",
        "us-sc/manual/2026-07-13-recovery",
        "us-ut/manual/2026-07-13-recovery",
    ):
        jurisdiction, document_class, version = key.split("/", 2)
        by_document: dict[str, list[dict[str, Any]]] = {}
        for row in _rows(key).values():
            by_document.setdefault(row["source_id"], []).append(row)
        for document_id, rows in by_document.items():
            first = rows[0]
            provenance = json.loads(
                (CORPUS_ROOT / "sources" / key / "provenance" / f"{document_id}.json").read_text(
                    encoding="utf-8"
                )
            )
            entry = {
                "document_id": document_id,
                "jurisdiction": jurisdiction,
                "document_class": document_class,
                "parser": first["metadata"]["recovery_parser"],
                "proposed_version": version,
                "covers_citation_paths": []
                if "/recovery/" in first["citation_path"]
                else [first["citation_path"]],
            }
            data = (CORPUS_ROOT / first["source_path"]).read_bytes()
            if first["kind"] == "section":
                _, records = _targeted_state_html(entry, data, provenance, first["source_path"])
            else:
                _, records = _generic(
                    entry, Path(document_id), data, provenance, first["source_path"]
                )
            assert [record.to_mapping() for record in records] == rows, (key, document_id)
            replayed += 1
    assert replayed == 38


def test_ny_ut_mt_rows_are_whole_pages_around_the_law_text() -> None:
    for key in (
        "us-ny/statute/2026-07-13-recovery",
        "us-ut/statute/2026-07-13-recovery",
        "us-mt/regulation/2026-07-13-recovery",
    ):
        assert set(_verdicts(key).values()) == {"page_text_with_chrome"}, key
    ny = _scope_audit("us-ny/statute/2026-07-13-recovery")["carriage"]
    assert len(ny) == 22
    assert all(entry["container_text_equals_carrier_text"] for entry in ny)
    for entry in _scope_audit("us-ut/statute/2026-07-13-recovery")["carriage"]:
        # Same words once markers are set aside; the page adds heading, effective
        # date and history, which the chapter scope keeps in metadata.
        assert entry["carrier_words_not_in_container"] == 0
        assert entry["container_words_not_in_carrier"] == 19


def test_hollow_statute_scopes_hold_only_chrome_or_already_carried_text() -> None:
    assert _scope_audit("us-id/statute/2026-07-13-recovery")["summary"]["verdicts"] == {
        "empty_document_root": 5,
        "site_chrome": 10,
    }
    me = _verdicts("us-me/statute/2026-07-13-recovery")
    assert [path for path, verdict in me.items() if verdict == "legal_text"] == [
        "us-me/statute/36/5111/block-2"
    ]
    for key in (
        "us-me/statute/2026-07-13-recovery",
        "us-mn/statute/2026-07-13-recovery",
    ):
        for entry in _scope_audit(key)["carriage"]:
            assert entry["carrier_words_not_in_container"] == 0
            if "text_lines" in entry:
                assert entry["text_lines_in_carrier_text"] == entry["text_lines"], entry
    for entry in _scope_audit("us-id/statute/2026-07-13-recovery")["carriage"]:
        assert entry["carrier_text_in_container_text"] is True


def test_sc_block_2_is_other_sections_tables_and_nothing_carries_12_6_520() -> None:
    from axiom_corpus.corpus.state_adapters.south_carolina import (
        parse_south_carolina_chapter_html,
    )

    rows = {
        row["citation_path"]: row
        for row in _scope_audit("us-sc/statute/2026-07-13-recovery")["rows"]
    }
    block = rows["us-sc/statute/12-6-520/block-2"]
    assert block["verdict"] == "tables_from_other_sections"
    assert block["sections"] == ["12-6-3535", "12-6-3910", "12-6-510", "12-6-545"]
    carriers = [
        path
        for path in sorted((CORPUS_ROOT / "provisions/us-sc/statute").glob("*.jsonl"))
        if any(
            json.loads(line)["citation_path"] == "us-sc/statute/12-6-520"
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        )
    ]
    assert [path.stem for path in carriers] == ["2026-07-13-recovery"]
    page = next(iter(_rows("us-sc/statute/2026-07-13-recovery").values()))["source_path"]
    chapter_pages = {
        (CORPUS_ROOT / page).read_bytes(),
        *(
            (
                CORPUS_ROOT
                / "sources/us-sc/statute"
                / version
                / "south-carolina-code-html/title-12/chapter-6.html"
            ).read_bytes()
            for version in (
                "2026-07-16-pit-central-us-sc-title-12-chapter-6",
                "2026-07-24-sc-act110-us-sc-title-12-chapter-6",
            )
        ),
    }
    assert len(chapter_pages) == 1
    sections = parse_south_carolina_chapter_html(
        (CORPUS_ROOT / page).read_bytes(), title=12, chapter="6"
    )
    [section] = [section for section in sections if section.section == "12-6-520"]
    assert section.heading == (
        "Annual adjustments to individual state income tax brackets; inflation adjustments"
    )
    assert (section.body or "").startswith("Beginning on December 15, 2018")


def test_alias_rows_copy_whole_sections_and_pages() -> None:
    mi = [
        row
        for row in _scope_audit("us-mi/statute/2026-07-13-recovery")["rows"]
        if row["verdict"] == "alias_copy"
    ]
    assert len(mi) == 10
    assert {row["copies"] for row in mi} == {
        "us-mi/statute/recovery/us-mi-code-206.30/block-1",
        "us-mi/statute/recovery/us-mi-code-206.51/block-1",
    }
    co = {
        row["citation_path"].rsplit("/", 1)[1]: (
            row["copies"].rsplit("/", 1)[1],
            row["opens_with_target"],
        )
        for row in _scope_audit("us-co/regulation/2026-07-13-recovery")["rows"]
        if row["verdict"] == "alias_copy"
    }
    # 3.606.1 is a copy of the rule's amendment-history page.
    assert co == {
        "3.606.1": ("page-110", False),
        "3.606.2": ("page-53", False),
        "3.606.6": ("page-61", True),
    }
    consolidated = _verdicts("us-co/regulation/2026-07-13-recovery-r2026-09-11-tanf-consolidated")
    for label in ("3.606.1", "3.606.2", "3.606.6"):
        assert consolidated[f"us-co/regulation/9-ccr-2503-6/{label}"] == "document_section_text"


def test_il_dedup_row_duplicates_the_manual_block_under_its_bodyless_root() -> None:
    dedup = _rows("us-il/manual/2026-07-13-recovery-r2026-07-17-dedup")
    manual = _rows("us-il/manual/2026-05-27-il-cash-snap-medical-manual-r2026-07-15-self-contained")
    assert not (manual["us-il/manual/dhs/csmm/19812"].get("body") or "").strip()
    assert (
        dedup["us-il/manual/dhs/csmm/19812/block-2"]["body"]
        == manual["us-il/manual/dhs/csmm/19812/block-1"]["body"]
    )


def test_landing_scopes_hold_no_legal_text() -> None:
    for key in (
        "us-fl/regulation/2026-07-13-recovery",
        "us-sc/regulation/2026-07-13-recovery",
        "us-tn/regulation/2026-07-13-recovery",
        "us-in/manual/2026-07-13-recovery",
        "us-sc/manual/2026-07-13-recovery",
        "us-ut/manual/2026-07-13-recovery",
    ):
        summary = _scope_audit(key)["summary"]
        assert summary["rows_without_legal_text"] == summary["rows"], key
    guidance = _scope_audit("us/guidance/2026-07-13-recovery")["rows"]
    fallbacks = [row for row in guidance if row.get("extractor_fallback")]
    assert len(fallbacks) == 3
    assert all(row["verdict"] == "landing_page_text" for row in fallbacks)


def _mutations() -> list[tuple[str, str, Any]]:
    def drop_first(body: str) -> str:
        return body.split("\n\n", 1)[1]

    def drop_last(body: str) -> str:
        return body.rsplit("\n\n", 1)[0]

    def truncate(body: str) -> str:
        return body[: len(body) // 2]

    def edit(body: str) -> str:
        return body.replace("e", "E", 1)

    return [
        ("us-id/statute/2026-07-13-recovery", "us-id/statute/63-3024/block-1", drop_first),
        ("us-mn/statute/2026-07-13-recovery", "us-mn/statute/290.0121/block-7", drop_last),
        ("us-mn/statute/2026-07-13-recovery", "us-mn/statute/290.0121/block-10", truncate),
        ("us-me/statute/2026-07-13-recovery", "us-me/statute/36/5111/block-2", edit),
        ("us-sc/statute/2026-07-13-recovery", "us-sc/statute/12-6-520/block-2", drop_first),
        ("us-ny/statute/2026-07-13-recovery", "us-ny/statute/TAX/673", edit),
        ("us-ut/statute/2026-07-13-recovery", "us-ut/statute/59-10-104", truncate),
        (
            "us-tn/regulation/2026-07-13-recovery",
            "us-tn/regulation/recovery/release-scope-us-tn-regulation-2026-05-29/block-1",
            drop_last,
        ),
    ]


@pytest.mark.parametrize(("key", "citation_path", "mutate"), _mutations())
def test_classifier_refuses_altered_rows(key: str, citation_path: str, mutate: Any) -> None:
    scope = BY_KEY[key]
    rows = _rows(key)
    row = dict(rows[citation_path])
    document_rows = [other for other in rows.values() if other["source_id"] == row["source_id"]]
    page = read_page(
        (CORPUS_ROOT / row["source_path"]).read_bytes(),
        scope.container,
        history=scope.history,
        section_markers=row["source_id"] in scope.section_marker_pages,
    )

    def verdict() -> str:
        result = classify_row(row, scope=scope, page=page, pdf=None, document_rows=document_rows)
        return str(result["verdict"])

    assert verdict() != "unclassified"
    row["body"] = mutate(row["body"])
    assert verdict() == "unclassified"


FOREIGN = "\u2603"  # a character that occurs in no audited row


@pytest.mark.parametrize("key", [scope.key for scope in SCOPES])
def test_no_row_with_text_foreign_to_its_source_is_classified(key: str) -> None:
    """Invariant over every row: a verdict means the body is text the source yields.

    Splicing a character that occurs in no row into any row's body, at its start,
    middle and end, makes that row ``unclassified``.
    """
    scope = BY_KEY[key]
    sources = load_sources(CORPUS_ROOT, REPO_ROOT, scope)
    for row in sources.rows:
        body = row.get("body") or ""
        assert FOREIGN not in body
        for position in sorted({0, len(body) // 2, len(body)}):
            mutated = dict(row, body=body[:position] + FOREIGN + body[position:])
            result = sources.classify(mutated, scope)
            assert result["verdict"] == "unclassified", (row["citation_path"], position)


def test_extractor_fallback_requires_a_page_without_body_blocks() -> None:
    """A page's whole content root is a verdict only where the extractor falls back."""
    scope = BY_KEY["us-tn/regulation/2026-07-13-recovery"]
    sources = load_sources(CORPUS_ROOT, REPO_ROOT, scope)
    [row] = [row for row in sources.rows if row.get("body")]
    page = sources.pages[row["source_id"]]
    assert page.runs() and page.root_text != row["body"]
    assert sources.classify(dict(row, body=page.root_text), scope)["verdict"] == "unclassified"
    guidance = BY_KEY["us/guidance/2026-07-13-recovery"]
    fallback = load_sources(CORPUS_ROOT, REPO_ROOT, guidance)
    for candidate in fallback.rows:
        if candidate["source_id"] in guidance.landing and candidate.get("body"):
            landing = fallback.pages[candidate["source_id"]]
            assert not landing.runs()
            assert candidate["body"] == landing.root_text


def test_no_text_verdicts_are_the_documented_ones() -> None:
    assert NO_TEXT_VERDICTS == (
        "empty_document_root",
        "site_chrome",
        "tables_from_other_sections",
        "landing_page_text",
    )
    assert BY_KEY["us-mn/statute/2026-07-13-recovery"].history == "div.history"


def test_release_validation_does_not_see_the_defects() -> None:
    """The gate passes every audited scope alone; only this audit records the defects."""
    for scope in SCOPES:
        report = _validate(scope.jurisdiction, scope.document_class, scope.version)
        assert (report["ok"], report["issue_count"]) == (True, 0), scope.key


@pytest.mark.parametrize(
    "key",
    [
        "us-ny/statute/2026-07-13-recovery",
        "us-me/statute/2026-07-13-recovery",
        "us-mn/statute/2026-07-13-recovery",
        "us-ut/statute/2026-07-13-recovery",
        "us-mi/statute/2026-07-13-recovery",
        "us-co/regulation/2026-07-13-recovery",
    ],
)
def test_the_proposed_swap_validates_on_the_obbb_line(key: str) -> None:
    jurisdiction, document_class, version = key.split("/", 2)
    swap = SWAPS[key]
    selected = _selector_versions(OBBB, jurisdiction, document_class)
    dropped = {version} | {item.split("/", 2)[2] for item in swap.get("drop_with", [])}
    added = [item.split("/", 2)[2] for item in swap["add"]]
    assert dropped <= set(selected)
    swapped = [v for v in selected if v not in dropped] + added
    report = _validate(jurisdiction, document_class, *swapped)
    assert (report["ok"], report["issue_count"]) == (True, 0), report["issues"][:3]
    # The newest wave4 cut already made this swap.
    wave4 = set(_selector_versions(WAVE4_R2, jurisdiction, document_class))
    assert version not in wave4 and set(added) <= wave4


def test_downstream_record_matches_the_audit() -> None:
    record = _downstream()
    assert len(record["axiom_encode_rev"]) == 40 and len(record["rulespec_us_rev"]) == 40
    assert set(record["scopes"]) == set(BY_KEY) == set(SWAPS)
    for key, lines in record["scopes"].items():
        verdicts = _verdicts(key)
        version = key.split("/", 2)[2]
        for line in lines.values():
            for entry in line["affected"]:
                today = entry["today"]
                if today.get("resolved_version") == version:
                    assert today["resolved_path"] in verdicts
                    for component in today["composed_from"]:
                        assert component in verdicts


def _affected(key: str, line: str) -> dict[str, dict[str, Any]]:
    entries = _downstream()["scopes"][key][line]["affected"]
    return {entry["cited_path"]: entry for entry in entries}


def test_downstream_effects_that_decide_the_swaps() -> None:
    # Dropping SC or MT without a successor dangles a cited path in every line.
    for key, path in (
        ("us-sc/statute/2026-07-13-recovery", "us-sc/statute/12-6-520"),
        (
            "us-mt/regulation/2026-07-13-recovery",
            "us-mt/regulation/title-37/chapter-37-78/subchapter-37-78-4/rule-37-78-420",
        ),
    ):
        for line in (OBBB, WAVE4_R2):
            entry = _affected(key, line)[path]
            assert entry["today"]["resolved_version"] == "2026-07-13-recovery"
            assert entry["after_swap"]["error"] == "CorpusSourceNotFoundError"
    # The IL dedup row breaks a cited path today; dropping the scope fixes it.
    for line in (OBBB, WAVE4_R2):
        entry = _affected("us-il/manual/2026-07-13-recovery-r2026-07-17-dedup", line)[
            "us-il/manual/dhs/csmm/19812"
        ]
        assert "cross active release scopes" in entry["today"]["message"]
        assert entry["after_swap"]["resolved_version"] == (
            "2026-05-27-il-cash-snap-medical-manual-r2026-07-15-self-contained"
        )
    # us/guidance is the only selected carrier of five cited ED and IRS paths.
    guidance = _affected("us/guidance/2026-07-13-recovery", WAVE4_R2)
    assert len(guidance) == 5
    assert all("error" in entry["after_swap"] for entry in guidance.values())
    # The statute swaps keep every cited path resolving except the block paths
    # the wave4 consolidation already listed as dangling.
    dangling = {
        path
        for key in SWAPS
        for line in _downstream()["scopes"][key].values()
        for path, entry in {e["cited_path"]: e for e in line["affected"]}.items()
        if "error" in entry["after_swap"] and "/statute/" in key
    }
    assert dangling == {
        "us-me/statute/36/5111/block-2",
        "us-mn/statute/290.06/block-12",
        "us-mn/statute/290.06/block-13",
        "us-sc/statute/12-6-520",
    }


def test_run_note_names_the_commands() -> None:
    note = RUN_NOTE.read_text(encoding="utf-8")
    assert "uv run --extra dev python scripts/audit_recovery_sibling_scopes.py" in note
    assert "scripts/resolve_recovery_sibling_citations.py" in note
