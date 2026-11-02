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
from itertools import chain
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest
from hypothesis import Phase, example, given, settings
from hypothesis import strategies as st

from tests.corpus_scan import corpus_scan

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema" / "citation-path.v1.json"
PROVISIONS_DIR = REPO_ROOT / "data" / "corpus" / "provisions"

# The module-scoped `result` fixture parses the whole corpus, and pytest-timeout
# charges that setup to whichever test first requests it. Under CI's flat 60 s a
# slow scan errored all eight corpus tests (axiom-corpus#736), so the corpus-sized
# budget covers the whole module, including its fast tmp_path tests.
pytestmark = corpus_scan

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


PROPOSAL_SECURITY_VERSIONS = (
    "2026-09-28-federal-proposal-security-guidance",
    "2026-08-30-proposal-security-title-2-part-25",
    "2026-08-30-proposal-security-title-45-part-604",
    "2026-08-30-proposal-security-title-31",
    "2026-08-30-proposal-security-title-42",
)
PROPOSAL_SECURITY_RATCHETS = ("endash_segments", "uppercase_segments")


@pytest.fixture(scope="module")
def proposal_security_path_sets():
    # A partial checkout could falsely justify lowering main's ratchets.
    assert validate_mod.unfetched_locked_provisions(PROVISIONS_DIR) == []
    grouped = {
        version: {family: set() for family in PROPOSAL_SECURITY_RATCHETS}
        for version in (None, *PROPOSAL_SECURITY_VERSIONS)
    }
    seen = set()
    for record in validate_mod.iter_records(PROVISIONS_DIR):
        assert "_error" not in record, record
        version = record.get("version")
        if version in PROPOSAL_SECURITY_VERSIONS:
            seen.add(version)
        else:
            version = None
        path = record["citation_path"]
        for family in PROPOSAL_SECURITY_RATCHETS:
            if validate_mod.IRREGULAR_PREDICATES[family](path):
                grouped[version][family].add(path)
    assert seen == set(PROPOSAL_SECURITY_VERSIONS)
    return grouped


@settings(max_examples=20, deadline=None)
@example(scope_order=[])
@example(scope_order=list(PROPOSAL_SECURITY_VERSIONS))
@example(scope_order=list(PROPOSAL_SECURITY_VERSIONS) * 2)
@given(scope_order=st.lists(st.sampled_from(PROPOSAL_SECURITY_VERSIONS), max_size=10))
def test_proposal_security_ratchets_preserve_main_for_any_scope_selection(
    schema, proposal_security_path_sets, scope_order
):
    # Main plus any selection of this pack must fit the merged ceilings;
    # repeated immutable scopes and scope ordering cannot increase counts.
    for family in PROPOSAL_SECURITY_RATCHETS:
        paths = proposal_security_path_sets[None][family].union(
            *(proposal_security_path_sets[version][family] for version in scope_order)
        )
        ceiling = schema["known_irregulars_ratchet"]["baselines"][family]
        assert len(paths) <= ceiling, (family, len(paths), ceiling)


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


def test_ratchet_counts_unique_citation_identities(tmp_path, schema):
    tight = json.loads(json.dumps(schema))
    tight["known_irregulars_ratchet"]["baselines"]["collection_roots"] = 1
    duplicate = _good_record(path="us-zz/statute")
    provisions = _write_jsonl(tmp_path, [duplicate, duplicate])

    result = validate_mod.validate(provisions, tight)

    assert result["record_count"] == 2
    assert result["unique_path_count"] == 1
    assert result["irregular_live_counts"]["collection_roots"] == 1
    assert "collection_roots" not in result["ratchet_regressions"]


def test_negative_invalid_json_line_is_caught(tmp_path, schema):
    provisions = _write_jsonl(tmp_path, [_good_record()])
    jsonl = next(provisions.rglob("*.jsonl"))
    with jsonl.open("a", encoding="utf-8") as handle:
        handle.write('{"citation_path": "us-zz/statute/1/b",\n')

    res = validate_mod.validate(provisions, schema)

    assert res["ok"] is False
    assert res["json_errors"] == [f"{jsonl}:2 invalid JSON"]
    assert res["record_count"] == 1


def test_scan_keeps_only_checked_fields(tmp_path):
    # The corpus-wide scan must not hold provision bodies: whole rows for the
    # 577,545-record corpus peaked at 6.1 GB and pushed this module's fixture
    # past the CI per-test timeout.
    rec = _good_record(body="x" * 10_000, heading="Heading", metadata={"a": [1, 2]})
    provisions = _write_jsonl(tmp_path, [rec])

    (streamed,) = validate_mod.iter_records(provisions)

    assert set(streamed) == set(validate_mod.CHECKED_FIELDS)
    assert streamed == {field: rec[field] for field in validate_mod.CHECKED_FIELDS}


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


@settings(phases=(Phase.generate,), max_examples=12, deadline=None)
@given(data=st.data())
def test_merged_uppercase_ceiling_ignores_version_duplicates_and_order(result, schema, data):
    # Reuse the real corpus scan's merged population size, then vary immutable
    # version multiplicity and order without parsing the corpus again.
    count = result["irregular_live_counts"]["uppercase_segments"]
    assert count > 0, "The real corpus must contain uppercase citation paths."
    paths = tuple(f"us/statute/ratchet-{index}/A" for index in range(count))
    duplicate_indices = data.draw(
        st.lists(st.integers(min_value=0, max_value=count - 1), min_size=1, max_size=64),
        label="immutable version duplicates",
    )
    rotation = data.draw(st.integers(min_value=0, max_value=count - 1), label="rotation")
    reverse = data.draw(st.booleans(), label="reverse order")
    ordered = paths[::-1] if reverse else paths

    def records(_provisions_dir):
        for path in chain(
            ordered[rotation:], ordered[:rotation], (paths[index] for index in duplicate_indices)
        ):
            yield {"citation_path": path}

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(validate_mod, "iter_records", records)
        res = validate_mod.validate(PROVISIONS_DIR, schema)

    assert res["record_count"] == count + len(duplicate_indices)
    assert res["irregular_live_counts"]["uppercase_segments"] == count
    assert res["ok"], res["ratchet_regressions"]
