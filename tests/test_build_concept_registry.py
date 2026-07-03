"""Hermetic unit tests for the concept-registry generator.

Builds a tiny fake ``rulespec-us`` tree in ``tmp_path`` and asserts the
extraction, typing, input inference, and PE-mapping join without needing the
real multi-thousand-file checkout (that end-to-end path is covered by
``test_concept_registry.py``'s skip-if-absent regeneration test).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
_GEN_PATH = REPO_ROOT / "scripts" / "build_concept_registry.py"
_spec = importlib.util.spec_from_file_location("build_concept_registry", _GEN_PATH)
assert _spec and _spec.loader
gen = importlib.util.module_from_spec(_spec)
sys.modules["build_concept_registry"] = gen
_spec.loader.exec_module(gen)


def _make_fake_rulespec_us(root: Path) -> None:
    """Create rulespec-us/us/statutes/7/2014/d.yaml + companion test."""
    mod_dir = root / "rulespec-us" / "us" / "statutes" / "7" / "2014"
    mod_dir.mkdir(parents=True)
    (mod_dir / "d.yaml").write_text(
        """\
format: rulespec/v1
rules:
  - name: quarter_cap
    kind: parameter
    dtype: Money
    unit: USD
    versions:
      - effective_from: '2008-10-01'
        formula: '30'
  - name: excluded_income
    kind: derived
    entity: Household
    dtype: Money
    period: Month
    unit: USD
    metadata:
      proof:
        atoms:
          - import:
              target: us:statutes/7/2014/d#quarter_cap
              output: quarter_cap
    versions:
      - effective_from: '2008-10-01'
        formula: |-
          if irregular_flag:
            min(irregular_amount, quarter_cap)
          else: 0
"""
    )
    (mod_dir / "d.test.yaml").write_text(
        """\
- name: case
  period: 2026-01
  input:
    us:statutes/7/2014/d#input.irregular_flag: true
    us:statutes/7/2014/d#input.irregular_amount: 45
  output:
    us:statutes/7/2014/d#quarter_cap: 30
    us:statutes/7/2014/d#excluded_income: 30
"""
    )


def _make_fake_encode(root: Path) -> None:
    p = root / "axiom-encode" / "src" / "axiom_encode" / "oracles" / "policyengine" / "mappings"
    p.mkdir(parents=True)
    (p / "us.yaml").write_text(
        """\
mappings:
  - legal_id: us:statutes/7/2014/d#excluded_income
    country: us
    program: snap
    mapping_type: direct_variable
    policyengine_variable: snap_excluded_income
  - legal_id: us:statutes/7/2014/d#quarter_cap
    country: us
    program: snap
    mapping_type: parameter_value
    policyengine_parameter: gov.usda.snap.quarter_cap
    comparison: count
prefixes: []
"""
    )


def test_build_extracts_and_joins(tmp_path: Path) -> None:
    _make_fake_rulespec_us(tmp_path)
    _make_fake_encode(tmp_path)

    result = gen.build(tmp_path, tmp_path / "axiom-encode", ["us"])
    assert "us.yaml" in result.files
    payload = yaml.safe_load(result.files["us.yaml"])

    assert payload["schema_version"] == gen.REGISTRY_SCHEMA_VERSION
    assert payload["jurisdiction"] == "us"
    # Provenance present (SHA may be None in a non-git tmp dir, key must exist).
    assert "rulespec_sha" in payload["generated_from"]
    assert payload["generated_from"]["rulespec_repo"] == "rulespec-us"

    by_id = {c["id"]: c for c in payload["concepts"]}

    # Outputs typed from the rule.
    cap = by_id["us:statutes/7/2014/d#quarter_cap"]
    assert cap["kind"] == "output"
    assert cap["dtype"] == "Money"
    assert cap["unit"] == "USD"
    assert cap["mappings"]["policyengine_us"]["parameter"] == "gov.usda.snap.quarter_cap"

    excl = by_id["us:statutes/7/2014/d#excluded_income"]
    assert excl["entity"] == "Household"
    assert excl["period"] == "Month"
    assert excl["mappings"]["policyengine_us"]["variable"] == "snap_excluded_income"

    # Inputs discovered from the test file; NO type guessed.
    for name in ("irregular_flag", "irregular_amount"):
        cid = f"us:statutes/7/2014/d#input.{name}"
        assert cid in by_id
        entry = by_id[cid]
        assert entry["kind"] == "input"
        assert "dtype" not in entry
        assert "unit" not in entry
        assert "period" not in entry

    # The imported output (quarter_cap) must NOT be misread as an input.
    assert "us:statutes/7/2014/d#input.quarter_cap" not in by_id
    # Rule names referenced in formulas must NOT be misread as inputs.
    assert "us:statutes/7/2014/d#input.excluded_income" not in by_id


def test_input_entity_inheritance_only_when_module_agrees(tmp_path: Path) -> None:
    # Module with a single entity -> inputs inherit it.
    mod = tmp_path / "rulespec-us" / "us" / "statutes" / "42" / "x"
    mod.mkdir(parents=True)
    (tmp_path / "rulespec-us" / "us" / "statutes" / "42" / "x.yaml").write_text(
        """\
format: rulespec/v1
rules:
  - name: is_eligible
    kind: derived
    entity: Person
    dtype: Judgment
    versions:
      - effective_from: '2020-01-01'
        formula: 'if applicant_flag: 1 else: 0'
"""
    )
    (tmp_path / "rulespec-us" / "us" / "statutes" / "42" / "x.test.yaml").write_text(
        """\
- name: c
  input:
    us:statutes/42/x#input.applicant_flag: true
  output:
    us:statutes/42/x#is_eligible: 1
"""
    )
    result = gen.build(tmp_path, tmp_path / "missing-encode", ["us"])
    payload = yaml.safe_load(result.files["us.yaml"])
    by_id = {c["id"]: c for c in payload["concepts"]}
    inp = by_id["us:statutes/42/x#input.applicant_flag"]
    assert inp["entity"] == "Person"  # module agrees on Person


def test_mixed_entity_module_leaves_inputs_untyped(tmp_path: Path) -> None:
    mod = tmp_path / "rulespec-us" / "us" / "statutes" / "7" / "y"
    mod.parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "rulespec-us" / "us" / "statutes" / "7" / "y.yaml").write_text(
        """\
format: rulespec/v1
rules:
  - name: hh_value
    kind: derived
    entity: Household
    dtype: Money
    versions:
      - effective_from: '2020-01-01'
        formula: 'shared_input + 1'
  - name: person_value
    kind: derived
    entity: Person
    dtype: Money
    versions:
      - effective_from: '2020-01-01'
        formula: 'shared_input + 2'
"""
    )
    (tmp_path / "rulespec-us" / "us" / "statutes" / "7" / "y.test.yaml").write_text(
        """\
- name: c
  input:
    us:statutes/7/y#input.shared_input: 10
  output:
    us:statutes/7/y#hh_value: 11
"""
    )
    result = gen.build(tmp_path, tmp_path / "missing-encode", ["us"])
    payload = yaml.safe_load(result.files["us.yaml"])
    by_id = {c["id"]: c for c in payload["concepts"]}
    inp = by_id["us:statutes/7/y#input.shared_input"]
    assert "entity" not in inp  # module disagrees -> never guess


def test_ambiguous_output_type_flagged(tmp_path: Path) -> None:
    # Two rules with the same name but different dtype -> type_ambiguous.
    d = tmp_path / "rulespec-us" / "us" / "statutes" / "1"
    d.mkdir(parents=True)
    (d / "a.yaml").write_text(
        """\
format: rulespec/v1
rules:
  - name: thing
    kind: parameter
    dtype: Money
    versions: [{effective_from: '2020-01-01', formula: '1'}]
  - name: thing
    kind: parameter
    dtype: Integer
    versions: [{effective_from: '2021-01-01', formula: '2'}]
"""
    )
    result = gen.build(tmp_path, tmp_path / "missing-encode", ["us"])
    payload = yaml.safe_load(result.files["us.yaml"])
    by_id = {c["id"]: c for c in payload["concepts"]}
    thing = by_id["us:statutes/1/a#thing"]
    assert thing.get("type_ambiguous") is True
    assert "dtype" not in thing  # conflicting -> dropped, not guessed
    assert thing["occurrences"] == 2


def test_check_and_write_roundtrip(tmp_path: Path) -> None:
    _make_fake_rulespec_us(tmp_path)
    _make_fake_encode(tmp_path)
    data_root = tmp_path / "out"

    result = gen.build(tmp_path, tmp_path / "axiom-encode", ["us"])
    # Before writing: check reports missing.
    assert gen.check_files(result, data_root)
    gen.write_files(result, data_root)
    # After writing: check is clean.
    assert gen.check_files(result, data_root) == []
    assert (data_root / "us.yaml").exists()

    # Writing a result that drops a jurisdiction removes the orphan file.
    empty = gen.BuildResult(files={}, summary={})
    gen.write_files(empty, data_root)
    assert not (data_root / "us.yaml").exists()


def test_uk_country_excluded_from_pe_edges(tmp_path: Path) -> None:
    # A uk module should never receive PE-US edges even if an id collides.
    d = tmp_path / "rulespec-uk" / "uk" / "statutes" / "1"
    d.mkdir(parents=True)
    (d / "a.yaml").write_text(
        """\
format: rulespec/v1
rules:
  - name: vat_amount
    kind: derived
    entity: Household
    dtype: Money
    versions: [{effective_from: '2020-01-01', formula: '1'}]
"""
    )
    result = gen.build(tmp_path, tmp_path / "missing-encode", ["uk"])
    payload = yaml.safe_load(result.files["uk.yaml"])
    assert "policyengine_mappings_sha" not in payload["generated_from"]
    for c in payload["concepts"]:
        assert "mappings" not in c
