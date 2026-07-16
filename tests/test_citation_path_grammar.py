"""Tests for the citation-path grammar (schema/citation-path.v1.json).

Two halves:

1. Positive: every current corpus citation_path validates, and the ratchets
   hold. This is the "all current paths validate against the grammar" gate from
   Phase-A item A6.
2. Negative (anti-vacuous): the validator provably REJECTS malformed paths,
   jurisdiction/document_class mismatches, ratchet regressions, and new identity
   drift. A green suite therefore means the checks can actually fail — not that
   there was nothing to check.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema" / "citation-path.v1.json"
PROVISIONS_DIR = REPO_ROOT / "data" / "corpus" / "provisions"

_spec = importlib.util.spec_from_file_location(
    "validate_citation_paths", REPO_ROOT / "scripts" / "validate_citation_paths.py"
)
validate_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(validate_mod)


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def result(schema) -> dict:
    return validate_mod.validate(PROVISIONS_DIR, schema)


# --------------------------------------------------------------------------
# Schema self-consistency
# --------------------------------------------------------------------------
def test_schema_is_valid_json_and_versioned(schema):
    assert schema["version"].startswith("1.")
    assert re.compile(schema["$defs"]["citation_path"]["pattern"])  # compiles
    assert set(schema["$defs"]["document_class"]["enum"]) == {
        "statute", "regulation", "manual", "guidance", "policy", "form", "rulemaking",
        "district-plan",
    }


def test_district_plan_class_paths_validate(tmp_path, schema):
    # The district-plan council-instrument class (schema v1.1) validates end to end:
    # a Wellington City district-plan provision path must pass the grammar and the
    # segment-1/document_class consistency check.
    pattern = re.compile(schema["$defs"]["citation_path"]["pattern"])
    path = "nz/district-plan/wellington-city/2024/muz/r13"
    assert pattern.match(path)
    provisions = _write_jsonl(
        tmp_path,
        [
            _good_record(path=path),
            _good_record(path="nz/district-plan/wellington-city/2024/giz/r5"),
            _good_record(path="nz/district-plan/wellington-city/2024/definitions/supermarket"),
        ],
    )
    res = validate_mod.validate(provisions, schema)
    assert res["ok"] is True, res
    assert res["pattern_failures"] == []
    assert res["unknown_docclass"] == []


def test_every_irregular_family_has_a_baseline(schema):
    families = set(validate_mod.IRREGULAR_PREDICATES)
    baselines = set(schema["known_irregulars_ratchet"]["baselines"])
    assert families == baselines, "predicate set and ratchet baselines must match exactly"


# --------------------------------------------------------------------------
# Positive: the real corpus validates
# --------------------------------------------------------------------------
def test_corpus_is_nonempty(result):
    # Guards against a silent "nothing scanned, therefore green" failure.
    assert result["record_count"] > 40000
    assert result["unique_path_count"] > 40000


def test_all_current_paths_match_grammar(result):
    assert result["pattern_failures"] == [], result["pattern_failures"][:20]


def test_no_json_errors(result):
    assert result["json_errors"] == []


def test_segment0_matches_jurisdiction_field(result):
    assert result["jurisdiction_mismatches"] == [], result["jurisdiction_mismatches"][:20]


def test_segment1_matches_document_class_field(result):
    assert result["docclass_mismatches"] == [], result["docclass_mismatches"][:20]
    assert result["unknown_docclass"] == [], result["unknown_docclass"][:20]


def test_irregular_families_within_ratchet(result):
    assert result["ratchet_regressions"] == {}, result["ratchet_regressions"]


def test_identity_drift_does_not_grow(result):
    # New drift (a path edited after its UUID was minted, not already tracked)
    # is a hard failure — that is the identity-corruption this grammar guards.
    assert result["identity_drift_new"] == [], result["identity_drift_new"]


def test_overall_ok(result):
    assert result["ok"] is True


# --------------------------------------------------------------------------
# Anti-vacuous negatives: the validator can actually reject bad input
# --------------------------------------------------------------------------
def _write_jsonl(tmp_path: Path, records: list[dict]) -> Path:
    d = tmp_path / "provisions" / "us-zz" / "statute"
    d.mkdir(parents=True)
    f = d / "2026-01-01-fixture.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return tmp_path / "provisions"


def _good_record(path: str = "us-zz/statute/1/a", **overrides) -> dict:
    rec = {
        "citation_path": path,
        "jurisdiction": path.split("/")[0],
        "document_class": path.split("/")[1],
        "version": "2026-01-01-fixture",
        "id": str(uuid5(NAMESPACE_URL, f"axiom:{path}")),
    }
    rec.update(overrides)
    return rec


def test_negative_pattern_violation_is_caught(tmp_path, schema):
    # Leading slash, empty segment, and an illegal char '@' all violate.
    bad = _good_record(path="us-zz/statute/1//bad@seg")
    prov = _write_jsonl(tmp_path, [bad])
    res = validate_mod.validate(prov, schema)
    assert res["ok"] is False
    assert res["pattern_failures"], "malformed path should be flagged"


def test_negative_bad_document_class_is_caught(tmp_path, schema):
    rec = _good_record(path="us-zz/newspaper/1/a", document_class="newspaper")
    prov = _write_jsonl(tmp_path, [rec])
    res = validate_mod.validate(prov, schema)
    assert res["ok"] is False
    # 'newspaper' is not in the enum -> pattern fails AND unknown_docclass fires.
    assert res["pattern_failures"] or res["unknown_docclass"]


def test_negative_jurisdiction_field_mismatch_is_caught(tmp_path, schema):
    rec = _good_record(path="us-zz/statute/1/a", jurisdiction="us-yy")
    prov = _write_jsonl(tmp_path, [rec])
    res = validate_mod.validate(prov, schema)
    assert res["ok"] is False
    assert res["jurisdiction_mismatches"]


def test_negative_ratchet_regression_is_caught(tmp_path, schema):
    # Force a block_n baseline of 0 so a single block-N path is a regression.
    tight = json.loads(json.dumps(schema))
    tight["known_irregulars_ratchet"]["baselines"]["block_n"] = 0
    rec = _good_record(path="us-zz/statute/1/block-1")
    prov = _write_jsonl(tmp_path, [rec])
    res = validate_mod.validate(prov, tight)
    assert res["ok"] is False
    assert "block_n" in res["ratchet_regressions"]


def test_negative_identity_drift_is_caught(tmp_path, schema):
    # Stored id that matches neither identity form == drift, and it's not in the
    # baseline list, so it must be reported as new.
    rec = _good_record(path="us-zz/statute/1/a", id="00000000-0000-5000-8000-000000000000")
    prov = _write_jsonl(tmp_path, [rec])
    res = validate_mod.validate(prov, schema)
    assert res["ok"] is False
    assert "us-zz/statute/1/a" in res["identity_drift_new"]


def test_positive_versioned_identity_is_accepted(tmp_path, schema):
    # A record whose id uses the *versioned* uuid5 form must NOT be flagged as drift.
    path = "us-zz/statute/1/a"
    version = "2026-01-01-fixture"
    identity = json.dumps(["axiom", version, path], separators=(",", ":"))
    rec = _good_record(path=path, version=version, id=str(uuid5(NAMESPACE_URL, identity)))
    prov = _write_jsonl(tmp_path, [rec])
    res = validate_mod.validate(prov, schema)
    assert res["identity_drift_new"] == []
    assert res["ok"] is True


def test_positive_multitoken_local_authority_jurisdiction_is_accepted(tmp_path, schema):
    path = "uk-kingston-upon-thames/manual/council-tax-reduction-scheme/page-42"
    rec = _good_record(path=path)
    prov = _write_jsonl(tmp_path, [rec])

    res = validate_mod.validate(prov, schema)

    assert res["pattern_failures"] == []
    assert res["jurisdiction_mismatches"] == []
    assert res["ok"] is True
