"""Tests for the NZ district-plan (IsoPlan council instrument) extractor.

The golden-file tests prove that the operative Wellington City 2024 District Plan
provisions the rulespec-nz#90 module grounds against — MUZ-R13, MUZ-R1, MUZ-P3,
GIZ-R5 — are reproduced verbatim from checked-in IsoPlan chapter payloads, at the
canonical ``nz/district-plan/...`` citation paths, so the module can re-point from
its guidance placeholder once the plan is ingested.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.district_plan import (
    DISTRICT_PLAN_DOCUMENT_CLASS,
    DistrictPlanManifest,
    classify_provision_kind,
    district_plan_citation_path,
    extract_nz_district_plan,
    parse_isoplan_chapter,
    parse_isoplan_definitions,
    parse_rule_identifier,
    provision_token_for_identifier,
    render_isoplan_text,
)
from axiom_corpus.corpus.models import ProvisionRecord

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "district_plan"
MUZ_FIXTURE = FIXTURES / "wellington-muz-231.json"
GIZ_FIXTURE = FIXTURES / "wellington-giz-235.json"
REV_FIXTURE = FIXTURES / "wellington-rev-137.json"

# rulespec-nz#90 proof excerpts — must be verbatim substrings of the resolved
# provision body for the encoding's grounding to resolve once ingested.
MUZ_R13_EXCERPTS = ("The total gross floor area does not exceed 1,500m", "Restricted Discretionary")
MUZ_R1_EXCERPT = "The activity is not a supermarket"
MUZ_P3_EXCERPT = "Only allow the establishment of integrated retail activities and large supermarkets"
GIZ_R5_EXCERPTS = (
    "The activity is trade supply retail, a wholesaler, a building improvement centre, "
    "service retail or yard based retail",
    "Non-complying",
    "Activity status: Permitted",
)
SUPERMARKET_DEFINITION_EXCERPT = "means a retail shop selling a wide range of foodstuffs"

# Live IsoPlan endpoints (from the manifest). The offline fetcher maps them to
# checked-in fixtures so no network access is needed.
MUZ_URL = "https://eplan.wellington.govt.nz/proposed/api/l/r/231/0/false/14-Jul-2026/false"
GIZ_URL = "https://eplan.wellington.govt.nz/proposed/api/l/r/235/0/false/14-Jul-2026/false"
REV_URL = "https://eplan.wellington.govt.nz/proposed/api/l/rev/137/14-Jul-2026/1"

_spec = importlib.util.spec_from_file_location(
    "validate_citation_paths", REPO_ROOT / "scripts" / "validate_citation_paths.py"
)
assert _spec and _spec.loader
validate_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_mod)


def _fixture_fetcher() -> Callable[[str], bytes]:
    payloads = {
        MUZ_URL: MUZ_FIXTURE.read_bytes(),
        GIZ_URL: GIZ_FIXTURE.read_bytes(),
        REV_URL: REV_FIXTURE.read_bytes(),
    }

    def fetch(url: str) -> bytes:
        try:
            return payloads[url]
        except KeyError as exc:  # pragma: no cover - guards a manifest/URL typo
            raise AssertionError(f"unexpected fetch URL: {url}") from exc

    return fetch


def _manifest_path(tmp_path: Path) -> Path:
    manifest = {
        "jurisdiction": "nz",
        "territorial_authority": "wellington-city",
        "territorial_authority_name": "Wellington City Council",
        "plan_version": "2024",
        "plan_title": "Wellington City 2024 District Plan",
        "plan_status": "operative",
        "revision": "137",
        "as_at": "14-Jul-2026",
        "base_url": "https://eplan.wellington.govt.nz/proposed/",
        "revision_index": {"url": REV_URL},
        "chapters": [
            {"code": "MUZ", "name": "Mixed Use Zone", "section_id": "231", "url": MUZ_URL},
            {"code": "GIZ", "name": "General Industrial Zone", "section_id": "235", "url": GIZ_URL},
        ],
    }
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    return path


def _run(tmp_path: Path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_nz_district_plan(
        store,
        manifest_path=_manifest_path(tmp_path),
        version="2026-07-16-nz-wellington-district-plan",
        retrieved_at="2026-07-15T00:00:00+00:00",
        fetcher=_fixture_fetcher(),
    )
    provisions_path = (
        tmp_path
        / "corpus"
        / "provisions"
        / "nz"
        / "district-plan"
        / "2026-07-16-nz-wellington-district-plan.jsonl"
    )
    records = {
        rec["citation_path"]: ProvisionRecord.from_mapping(rec)
        for rec in (json.loads(line) for line in provisions_path.read_text().splitlines() if line)
    }
    return report, records


# ---------------------------------------------------------------------------
# Text rendering
# ---------------------------------------------------------------------------
def test_render_preserves_inline_punctuation_spacing():
    # Glossary-term links carry their own trailing space inside the span, so the
    # renderer must not add a space at the inline boundary (no " , a wholesaler").
    html = (
        "<ol><li>The activity is "
        "<a href='' class='divRuleTextDef'>trade supply retail</a>"
        "<span>, a </span><a href=''>wholesaler</a><span> or "
        "</span><a href=''>yard based retail</a><span>.</span></li></ol>"
    )
    assert render_isoplan_text(html) == (
        "The activity is trade supply retail, a wholesaler or yard based retail."
    )


def test_render_breaks_on_block_boundaries_and_normalizes_entities():
    html = "<p>Activity status: <b>Permitted<br><br></b>Where:</p><p>Something&nbsp;else</p>"
    assert render_isoplan_text(html) == "Activity status: Permitted\nWhere:\nSomething else"


def test_render_superscript_keeps_measurement_readable():
    html = "<span>does not exceed 1,500m</span><sup>2</sup><span>.</span>"
    assert render_isoplan_text(html) == "does not exceed 1,500m2."


# ---------------------------------------------------------------------------
# Identifier parsing / tokens / kinds
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("cell", "identifier"),
    [
        ("MUZ-R13", "MUZ-R13"),
        ("MUZ-P3", "MUZ-P3"),
        ("GIZ-R5", "GIZ-R5"),
        ("MUZ-R10a", "MUZ-R10a"),
        ("MUZ-PREC01-R1", "MUZ-PREC01-R1"),
        ("M UZ-S11", "MUZ-S11"),  # source typo recovered by whitespace-stripped retry
        ("Objectives", None),
        ("Only allow the establishment", None),
    ],
)
def test_parse_rule_identifier(cell, identifier):
    assert parse_rule_identifier(cell) == identifier


def test_provision_token_drops_chapter_prefix():
    assert provision_token_for_identifier("MUZ-R13") == "r13"
    assert provision_token_for_identifier("MUZ-PREC01-R1") == "prec01-r1"
    assert provision_token_for_identifier("GIZ-R5") == "r5"


@pytest.mark.parametrize(
    ("identifier", "kind"),
    [
        ("MUZ-R13", "rule"),
        ("MUZ-P3", "policy"),
        ("MUZ-O1", "objective"),
        ("MUZ-S1", "standard"),
        ("MUZ-PREC01-R1", "rule"),
    ],
)
def test_classify_provision_kind(identifier, kind):
    assert classify_provision_kind(identifier) == kind


# ---------------------------------------------------------------------------
# Citation-path shape (the one canonical definition)
# ---------------------------------------------------------------------------
def test_citation_path_shape():
    assert (
        district_plan_citation_path(
            jurisdiction="nz",
            territorial_authority="wellington-city",
            plan_version="2024",
            chapter="muz",
            provision="r13",
        )
        == "nz/district-plan/wellington-city/2024/muz/r13"
    )
    assert (
        district_plan_citation_path(
            jurisdiction="nz", territorial_authority="wellington-city", plan_version="2024"
        )
        == "nz/district-plan/wellington-city/2024"
    )


def test_citation_path_requires_chapter_for_provision():
    with pytest.raises(ValueError):
        district_plan_citation_path(
            jurisdiction="nz",
            territorial_authority="wellington-city",
            plan_version="2024",
            provision="r13",
        )


# ---------------------------------------------------------------------------
# Chapter parsing (pure function, off the fixtures)
# ---------------------------------------------------------------------------
def test_parse_isoplan_chapter_muz():
    provisions = parse_isoplan_chapter(MUZ_FIXTURE.read_bytes(), chapter_code="MUZ")
    by_id = {p.identifier: p for p in provisions}
    # Every provision carries a plan identifier; narrative rows are not emitted.
    assert {"MUZ-O1", "MUZ-P3", "MUZ-R1", "MUZ-R13"} <= set(by_id)
    r13 = by_id["MUZ-R13"]
    assert r13.chapter_token == "muz"
    assert r13.provision_token == "r13"
    assert r13.kind == "rule"
    assert r13.heading == "Supermarkets"
    for excerpt in MUZ_R13_EXCERPTS:
        assert excerpt in r13.body
    # A provision's body must not bleed into the next provision.
    assert "Retirement Villages" not in r13.body
    assert MUZ_R1_EXCERPT in by_id["MUZ-R1"].body
    assert MUZ_P3_EXCERPT in by_id["MUZ-P3"].body
    assert by_id["MUZ-P3"].plan_section == "Policies"


def test_parse_isoplan_chapter_giz_r5_is_complete():
    provisions = parse_isoplan_chapter(GIZ_FIXTURE.read_bytes(), chapter_code="GIZ")
    r5 = next(p for p in provisions if p.identifier == "GIZ-R5")
    for excerpt in GIZ_R5_EXCERPTS:
        assert excerpt in r5.body
    # GIZ-R5's Non-complying limb references R5.1, not R6.
    assert "GIZ-R5.1" in r5.body
    assert "Sensitive activities" not in r5.body


def test_parse_isoplan_definitions():
    definitions = parse_isoplan_definitions(REV_FIXTURE.read_bytes())
    by_slug = {d.slug: d for d in definitions}
    assert "supermarket" in by_slug
    assert SUPERMARKET_DEFINITION_EXCERPT in by_slug["supermarket"].body


# ---------------------------------------------------------------------------
# End-to-end extraction (golden file)
# ---------------------------------------------------------------------------
def test_extract_writes_canonical_provisions(tmp_path):
    report, records = _run(tmp_path)
    assert report.document_class == DISTRICT_PLAN_DOCUMENT_CLASS == "district-plan"
    assert report.coverage.complete
    assert report.chapter_count == 2
    assert report.definition_count >= 1

    for path in (
        "nz/district-plan/wellington-city/2024",
        "nz/district-plan/wellington-city/2024/muz",
        "nz/district-plan/wellington-city/2024/muz/r13",
        "nz/district-plan/wellington-city/2024/muz/r1",
        "nz/district-plan/wellington-city/2024/muz/p3",
        "nz/district-plan/wellington-city/2024/giz/r5",
        "nz/district-plan/wellington-city/2024/definitions/supermarket",
    ):
        assert path in records, path


def test_extract_reproduces_rulespec_nz_90_excerpts(tmp_path):
    _, records = _run(tmp_path)
    r13 = records["nz/district-plan/wellington-city/2024/muz/r13"]
    for excerpt in MUZ_R13_EXCERPTS:
        assert excerpt in (r13.body or "")
    assert MUZ_R1_EXCERPT in (records["nz/district-plan/wellington-city/2024/muz/r1"].body or "")
    assert MUZ_P3_EXCERPT in (records["nz/district-plan/wellington-city/2024/muz/p3"].body or "")
    giz = records["nz/district-plan/wellington-city/2024/giz/r5"]
    for excerpt in GIZ_R5_EXCERPTS:
        assert excerpt in (giz.body or "")
    supermarket = records["nz/district-plan/wellington-city/2024/definitions/supermarket"]
    assert SUPERMARKET_DEFINITION_EXCERPT in (supermarket.body or "")


def test_extract_records_carry_provenance(tmp_path):
    _, records = _run(tmp_path)
    r13 = records["nz/district-plan/wellington-city/2024/muz/r13"]
    assert r13.kind == "rule"
    assert r13.legal_identifier == "MUZ-R13"
    assert r13.identifiers["district-plan:identifier"] == "MUZ-R13"
    assert r13.source_url == MUZ_URL
    assert r13.source_format == "isoplan-eplan-json"
    # Per-payload sha256 + retrieval timestamp + plan version pin.
    expected_sha = hashlib.sha256(MUZ_FIXTURE.read_bytes()).hexdigest()
    assert r13.metadata["source_sha256"] == expected_sha
    assert r13.metadata["retrieved_at"] == "2026-07-15T00:00:00+00:00"
    assert r13.metadata["revision"] == "137"
    assert r13.metadata["as_at"] == "14-Jul-2026"
    assert r13.identifiers["eplan:revision"] == "137"
    # "as at" 14-Jul-2026 becomes the ISO expression date.
    assert r13.expression_date == "2026-07-14"
    assert r13.source_as_of == "2026-07-15"


def test_extract_hierarchy_parents(tmp_path):
    _, records = _run(tmp_path)
    plan_root = records["nz/district-plan/wellington-city/2024"]
    chapter = records["nz/district-plan/wellington-city/2024/muz"]
    r13 = records["nz/district-plan/wellington-city/2024/muz/r13"]
    assert plan_root.parent_citation_path is None
    assert plan_root.level == 1
    assert chapter.parent_citation_path == plan_root.citation_path
    assert chapter.kind == "chapter"
    assert chapter.level == 2
    assert r13.parent_citation_path == chapter.citation_path
    assert r13.level == 3


def test_extract_sha256_matches_stored_source_snapshot(tmp_path):
    # The extractor snapshots the exact payload bytes it hashed.
    _run(tmp_path)
    snapshot = (
        tmp_path
        / "corpus"
        / "sources"
        / "nz"
        / "district-plan"
        / "2026-07-16-nz-wellington-district-plan"
        / "eplan"
        / "wellington-city"
        / "2024"
        / "muz-231.json"
    )
    assert snapshot.exists()
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == hashlib.sha256(
        MUZ_FIXTURE.read_bytes()
    ).hexdigest()


def test_extracted_paths_validate_against_citation_grammar(tmp_path):
    # Ties the extractor to the taxonomy deliverable: every emitted path passes the
    # corpus citation-path grammar (which now carries the district-plan class).
    _run(tmp_path)
    schema = json.loads((REPO_ROOT / "schema" / "citation-path.v1.json").read_text())
    provisions_dir = tmp_path / "corpus" / "provisions"
    result = validate_mod.validate(provisions_dir, schema)
    assert result["pattern_failures"] == [], result["pattern_failures"]
    assert result["unknown_docclass"] == [], result["unknown_docclass"]
    assert result["docclass_mismatches"] == [], result["docclass_mismatches"]
    assert result["jurisdiction_mismatches"] == [], result["jurisdiction_mismatches"]


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------
def test_repo_wellington_manifest_loads():
    manifest = DistrictPlanManifest.load(REPO_ROOT / "manifests" / "nz-wellington-district-plan.yaml")
    assert manifest.territorial_authority == "wellington-city"
    assert manifest.plan_version == "2024"
    assert manifest.revision == "137"
    codes = {chapter.code for chapter in manifest.chapters}
    assert {"CCZ", "MCZ", "MUZ", "LCZ", "NCZ", "GIZ"} <= codes
    assert manifest.revision_index_url is not None
