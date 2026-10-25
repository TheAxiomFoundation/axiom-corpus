from __future__ import annotations

import json
import shutil
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import NoReturn

import requests

from axiom_corpus.corpus.documents import OfficialDocumentManifest
from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest
from scripts.repro.us_ca_calfresh_bbce_authority import (
    CANONICAL_SOURCE_BY_INPUT,
    EXPECTED_EXCERPTS,
    EXPECTED_GUIDANCE_ROW_COUNT,
    EXPECTED_MCE_GATE_IDS,
    EXPECTED_MEMBER_EXCLUSIONS,
    EXPECTED_PAGE_COUNTS,
    EXPECTED_ROWS_BY_INPUT,
    EXPECTED_ROWS_BY_SOURCE_ID,
    EXPECTED_SHA256,
    EXPECTED_STATE_OVERLAY_BY_GATE,
    EXPECTED_STATUTE_CITATION_PATHS,
    EXPECTED_STATUTE_ROW_COUNT,
    FEDERAL_AUTHORITY_PROVISIONS,
    FEDERAL_AUTHORITY_SOURCE_AS_OF,
    FEDERAL_AUTHORITY_VERSION,
    FEDERAL_MCE_CITATION_PATH,
    FEDERAL_MCE_EXCLUSIONS_END,
    FEDERAL_MCE_EXCLUSIONS_SHA256,
    FEDERAL_MCE_EXCLUSIONS_START,
    FEDERAL_MEMBER_EXCLUSIONS_END,
    FEDERAL_MEMBER_EXCLUSIONS_SHA256,
    FEDERAL_MEMBER_EXCLUSIONS_START,
    FEDERAL_MEMBER_RULE_CITATION_PATH,
    GENERATED_RELATIVE_PATHS,
    GUIDANCE_COVERAGE,
    GUIDANCE_INPUT_BY_SOURCE_ID,
    GUIDANCE_INVENTORY,
    GUIDANCE_PROVISIONS,
    GUIDANCE_VERSION,
    MANIFEST_PATH,
    MCE_EXCLUSION_GATES,
    REPRO_COMMAND,
    ROOT_CITATION_BY_SOURCE_ID,
    STATUTE_COVERAGE,
    STATUTE_INVENTORY,
    STATUTE_PROVISIONS,
    STATUTE_VERSION,
    reproduce,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data/corpus"
RELEASE_PATH = (
    REPO_ROOT
    / "manifests/releases/us-ca-2026-07-28-calfresh-bbce-authority.json"
)
RUN_DOC_PATH = (
    REPO_ROOT
    / "docs/ingest-runs/2026-07-28-ca-calfresh-bbce-authority.md"
)
LITERAL_REPRO_COMMAND = (
    "uv run --extra dev python "
    "scripts/repro/us_ca_calfresh_bbce_authority.py --base data/corpus"
)


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _coverage(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_retained_sources_are_exact_and_scopes_are_complete() -> None:
    for input_name, relative_path in CANONICAL_SOURCE_BY_INPUT.items():
        content = (CORPUS_ROOT / relative_path).read_bytes()
        assert sha256(content).hexdigest() == EXPECTED_SHA256[input_name]

    guidance_rows = _jsonl(CORPUS_ROOT / GUIDANCE_PROVISIONS)
    statute_rows = _jsonl(CORPUS_ROOT / STATUTE_PROVISIONS)
    guidance_inventory = json.loads(
        (CORPUS_ROOT / GUIDANCE_INVENTORY).read_text(encoding="utf-8")
    )["items"]
    statute_inventory = json.loads(
        (CORPUS_ROOT / STATUTE_INVENTORY).read_text(encoding="utf-8")
    )["items"]

    assert (
        len(guidance_rows)
        == len(guidance_inventory)
        == EXPECTED_GUIDANCE_ROW_COUNT
    )
    assert (
        len(statute_rows)
        == len(statute_inventory)
        == EXPECTED_STATUTE_ROW_COUNT
    )
    assert Counter(row["source_id"] for row in guidance_rows) == Counter(
        EXPECTED_ROWS_BY_SOURCE_ID
    )
    assert {row["citation_path"] for row in statute_rows} == (
        EXPECTED_STATUTE_CITATION_PATHS
    )
    for statute_row in statute_rows:
        assert statute_row.get("parent_citation_path") is None
        assert statute_row.get("parent_id") is None
        assert statute_row["metadata"]["parent_citation_path"] == (
            "us-ca/statute/wic"
        )

    expected_guidance_paths: set[str] = set()
    for source_id, root_path in ROOT_CITATION_BY_SOURCE_ID.items():
        expected_guidance_paths.add(root_path)
        input_name = GUIDANCE_INPUT_BY_SOURCE_ID[source_id]
        expected_guidance_paths.update(
            f"{root_path}/page-{page}"
            for page in range(1, EXPECTED_PAGE_COUNTS[input_name] + 1)
        )
    assert {row["citation_path"] for row in guidance_rows} == expected_guidance_paths
    assert {item["citation_path"] for item in guidance_inventory} == (
        expected_guidance_paths
    )

    for path, document_class, version, count in (
        (
            GUIDANCE_COVERAGE,
            "guidance",
            GUIDANCE_VERSION,
            EXPECTED_GUIDANCE_ROW_COUNT,
        ),
        (
            STATUTE_COVERAGE,
            "statute",
            STATUTE_VERSION,
            EXPECTED_STATUTE_ROW_COUNT,
        ),
    ):
        coverage = _coverage(CORPUS_ROOT / path)
        assert coverage["complete"] is True
        assert coverage["document_class"] == document_class
        assert coverage["jurisdiction"] == "us-ca"
        assert coverage["version"] == version
        assert coverage["source_count"] == count
        assert coverage["provision_count"] == count
        assert coverage["matched_count"] == count
        assert coverage["missing_from_provisions"] == []
        assert coverage["extra_provisions"] == []
        assert coverage["duplicate_source_citations"] == []
        assert coverage["duplicate_provision_citations"] == []

    serialized_scope = json.dumps(
        guidance_rows + statute_rows + guidance_inventory + statute_inventory
    )
    assert "file://" not in serialized_scope


def test_rulespec_1098_parameters_have_retained_controlling_text() -> None:
    rows = _jsonl(CORPUS_ROOT / GUIDANCE_PROVISIONS) + _jsonl(
        CORPUS_ROOT / STATUTE_PROVISIONS
    )
    rows_by_path = {row["citation_path"]: row for row in rows}

    for citation_path, excerpts in EXPECTED_EXCERPTS.items():
        body = rows_by_path[citation_path]["body"]
        assert body is not None
        for excerpt in excerpts:
            assert excerpt in body


def test_mce_exclusion_map_is_exhaustive_against_current_retained_cfr() -> None:
    federal_rows = _jsonl(CORPUS_ROOT / FEDERAL_AUTHORITY_PROVISIONS)
    federal_by_path = {row["citation_path"]: row for row in federal_rows}
    mce_row = federal_by_path[FEDERAL_MCE_CITATION_PATH]
    member_rule_row = federal_by_path[FEDERAL_MEMBER_RULE_CITATION_PATH]
    for row in (mce_row, member_rule_row):
        assert row["version"] == FEDERAL_AUTHORITY_VERSION
        assert row["source_as_of"] == FEDERAL_AUTHORITY_SOURCE_AS_OF

    mce_body = mce_row["body"]
    start = mce_body.index(FEDERAL_MCE_EXCLUSIONS_START)
    end = mce_body.index(FEDERAL_MCE_EXCLUSIONS_END, start)
    exclusion_clause = mce_body[start:end]
    assert sha256(exclusion_clause.encode("utf-8")).hexdigest() == (
        FEDERAL_MCE_EXCLUSIONS_SHA256
    )

    member_start = mce_body.index(FEDERAL_MEMBER_EXCLUSIONS_START)
    member_end = mce_body.index(FEDERAL_MEMBER_EXCLUSIONS_END, member_start)
    member_clause = mce_body[member_start:member_end]
    assert sha256(member_clause.encode("utf-8")).hexdigest() == (
        FEDERAL_MEMBER_EXCLUSIONS_SHA256
    )
    assert len(EXPECTED_MEMBER_EXCLUSIONS) == 5
    for excerpt in EXPECTED_MEMBER_EXCLUSIONS.values():
        assert excerpt in member_clause

    assert set(MCE_EXCLUSION_GATES) == EXPECTED_MCE_GATE_IDS
    assert Counter(
        gate["federal_clause"] for gate in MCE_EXCLUSION_GATES.values()
    ) == Counter({"A": 2, "B": 1, "C": 1, "D": 3})
    assert {
        gate_id: gate["state_overlay_citation_path"]
        for gate_id, gate in MCE_EXCLUSION_GATES.items()
        if gate["state_overlay_citation_path"] is not None
    } == EXPECTED_STATE_OVERLAY_BY_GATE

    guidance_by_path = {
        row["citation_path"]: row
        for row in _jsonl(CORPUS_ROOT / GUIDANCE_PROVISIONS)
    }
    statute_by_path = {
        row["citation_path"]: row
        for row in _jsonl(CORPUS_ROOT / STATUTE_PROVISIONS)
    }
    member_rule_body = member_rule_row["body"]
    for gate in MCE_EXCLUSION_GATES.values():
        assert gate["federal_citation_path"] == FEDERAL_MCE_CITATION_PATH
        assert gate["federal_excerpt"] in exclusion_clause
        if gate["supporting_federal_citation_path"] is not None:
            assert (
                gate["supporting_federal_citation_path"]
                == FEDERAL_MEMBER_RULE_CITATION_PATH
            )
            assert gate["supporting_federal_excerpt"] in member_rule_body
        else:
            assert gate["supporting_federal_excerpt"] is None

        state_path = gate["state_overlay_citation_path"]
        if state_path is None:
            assert gate["state_overlay_excerpts"] == ()
        else:
            state_body = statute_by_path[state_path]["body"]
            for state_excerpt in gate["state_overlay_excerpts"]:
                assert state_excerpt in state_body
        for context_path in gate["guidance_context_citation_paths"]:
            assert context_path in guidance_by_path

    assert MCE_EXCLUSION_GATES["drug_felony_member_ineligibility"][
        "california_result"
    ] == "conviction_alone_does_not_trigger_the_gate_after_state_opt_out"
    assert MCE_EXCLUSION_GATES[
        "fleeing_felon_or_probation_parole_violator"
    ]["california_result"].startswith("federal_gate_controls_universally")


def test_zero_benefit_authority_prefers_acl_14_63() -> None:
    manifest = OfficialDocumentManifest.load(MANIFEST_PATH)
    sources = {source.source_id: source for source in manifest.documents}
    primary = sources["ca-cdss-acl-2014-14-63"]
    context = sources["ca-cdss-acl-2014-14-56"]

    assert primary.metadata["authority_role"] == (
        "focused_zero_benefit_denial_and_discontinuance_policy"
    )
    assert context.metadata["authority_role"] == (
        "statewide_bbce_trigger_and_200_percent_fpl_screen"
    )
    assert sources["ca-cdss-acl-2014-14-56"].extraction[
        "text_replacements"
    ] == {
        (
            "California Department of Social Services Letterhead inclusive of "
            "the California Department of Social Services Organizational Logo "
            "and the State Seal of California"
        ): ""
    }
    assert sources["ca-cdss-acl-2013-13-32"].extraction[
        "text_replacements"
    ] == {
        "CDSS Letterhead": "",
        "Great Seal of California, Edmund G. Brown Jr. Governor": "",
    }


def test_round_one_rows_are_conserved_semantically() -> None:
    prior_fields = (
        "citation_path",
        "body",
        "heading",
        "source_id",
        "source_url",
        "source_format",
        "source_as_of",
        "expression_date",
        "metadata",
    )
    all_rows = _jsonl(CORPUS_ROOT / GUIDANCE_PROVISIONS) + _jsonl(
        CORPUS_ROOT / STATUTE_PROVISIONS
    )
    prior_rows = [
        row
        for row in all_rows
        if row.get("source_id") != "ca-cdss-acl-2014-14-63"
        and row.get("citation_path") != "us-ca/statute/wic/18901.3"
    ]
    assert len(prior_rows) == 45
    assert len({row["citation_path"] for row in prior_rows}) == 45
    projection = [
        {field: row.get(field) for field in prior_fields}
        for row in sorted(prior_rows, key=lambda row: row["citation_path"])
    ]
    payload = json.dumps(
        projection,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert sha256(payload).hexdigest() == (
        "6a79caf1945521a9d13aaf58248cd453a1d938b545d309d6b3f4b570fed68edd"
    )


def test_offline_reproduction_is_byte_deterministic(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_dir = tmp_path / "flat-sources"
    source_dir.mkdir()
    for input_name, relative_path in CANONICAL_SOURCE_BY_INPUT.items():
        shutil.copyfile(CORPUS_ROOT / relative_path, source_dir / input_name)

    def fail_network(*_args, **_kwargs) -> NoReturn:
        raise AssertionError("offline reproducer attempted network access")

    monkeypatch.setattr(requests.sessions.Session, "request", fail_network)
    replay_base = tmp_path / "replayed-corpus"
    report = reproduce(replay_base, source_dir)

    assert report["command"] == REPRO_COMMAND == LITERAL_REPRO_COMMAND
    assert report["mce_exclusion_gate_count"] == 7
    assert report["per_source_rows"] == EXPECTED_ROWS_BY_INPUT
    for relative_path in GENERATED_RELATIVE_PATHS:
        assert (replay_base / relative_path).read_bytes() == (
            CORPUS_ROOT / relative_path
        ).read_bytes()


def test_repro_command_is_literal_and_release_passes_strictly() -> None:
    run_doc = RUN_DOC_PATH.read_text(encoding="utf-8")
    assert f"```bash\n{LITERAL_REPRO_COMMAND}\n```" in run_doc

    release = ReleaseManifest.load(RELEASE_PATH)
    assert release.name == "us-ca-2026-07-28-calfresh-bbce-authority"
    assert release.scope_keys == (
        ("us-ca", "guidance", GUIDANCE_VERSION),
        ("us-ca", "statute", STATUTE_VERSION),
    )
    report = validate_release(
        CORPUS_ROOT,
        release,
        strict_warnings=True,
        max_issues=200,
    )
    assert report.to_mapping() == {
        "release": "us-ca-2026-07-28-calfresh-bbce-authority",
        "scope_count": 2,
        "ok": True,
        "error_count": 0,
        "warning_count": 0,
        "strict_warnings": True,
        "issue_count": 0,
        "issues_returned": 0,
        "issues_truncated": False,
        "issues": [],
    }
