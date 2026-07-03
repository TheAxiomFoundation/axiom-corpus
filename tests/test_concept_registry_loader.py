"""Unit tests for the concept-registry loader with small in-memory fixtures.

These are hermetic (no ``rulespec-*`` checkout, no packaged data) and fast:
they write tiny registry files to ``tmp_path`` and assert the loader's parsing,
helper methods, and error paths.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axiom_corpus.concepts import (
    REGISTRY_SCHEMA_VERSION,
    Concept,
    ConceptMapping,
    ConceptRegistry,
    load_concept_registry,
    load_jurisdiction_file,
)

_HEADER = f"""\
schema_version: {REGISTRY_SCHEMA_VERSION}
registry_version: "0.1.0"
jurisdiction: us
generated_from:
  rulespec_repo: rulespec-us
  rulespec_sha: deadbeef
concepts:
"""


def _write(dir_: Path, name: str, body: str) -> Path:
    path = dir_ / name
    path.write_text(_HEADER + body)
    return path


def test_loads_output_and_input(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "us.yaml",
        """\
- id: us:statutes/7/2014/d#foo
  kind: output
  name: foo
  dtype: Money
  entity: Household
  period: Month
  unit: USD
  modules: [us:statutes/7/2014/d]
  occurrences: 3
  mappings:
    policyengine_us:
      mapping_type: direct_variable
      variable: snap_foo
- id: us:statutes/7/2014/d#input.bar
  kind: input
  name: bar
  modules: [us:statutes/7/2014/d]
  occurrences: 2
""",
    )
    reg = load_concept_registry(tmp_path)
    assert len(reg) == 2
    assert len(reg.outputs()) == 1
    assert len(reg.inputs()) == 1

    foo = reg.get("us:statutes/7/2014/d#foo")
    assert foo is not None
    assert foo.is_output and not foo.is_input
    assert foo.is_typed
    assert foo.dtype == "Money"
    assert foo.entity == "Household"
    edge = foo.mapping_for("policyengine_us")
    assert edge is not None and edge.variable == "snap_foo"
    assert foo.mapping_for("taxsim") is None

    bar = reg.get("us:statutes/7/2014/d#input.bar")
    assert bar is not None and bar.is_input
    assert bar.dtype is None
    assert not bar.is_typed

    assert reg.with_mapping("policyengine_us") == [foo]
    assert reg.get("missing") is None


def test_type_ambiguous_flag(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "us.yaml",
        """\
- id: us:x#amb
  kind: output
  name: amb
  type_ambiguous: true
  modules: [us:x]
  occurrences: 1
""",
    )
    reg = load_concept_registry(tmp_path)
    amb = reg.get("us:x#amb")
    assert amb is not None
    assert amb.type_ambiguous is True
    assert amb.is_typed is False  # ambiguous never counts as typed


def test_duplicate_id_across_files_raises(tmp_path: Path) -> None:
    body = """\
- id: us:x#dup
  kind: output
  name: dup
  modules: [us:x]
  occurrences: 1
"""
    _write(tmp_path, "a.yaml", body)
    _write(tmp_path, "b.yaml", body)
    with pytest.raises(ValueError, match="Duplicate concept id"):
        load_concept_registry(tmp_path)


def test_bad_schema_version_raises(tmp_path: Path) -> None:
    (tmp_path / "us.yaml").write_text(
        "schema_version: wrong/v9\njurisdiction: us\nconcepts: []\n"
    )
    with pytest.raises(ValueError, match="unsupported schema_version"):
        load_jurisdiction_file(tmp_path / "us.yaml")


def test_non_mapping_file_raises(tmp_path: Path) -> None:
    (tmp_path / "us.yaml").write_text("- just\n- a\n- list\n")
    with pytest.raises(ValueError, match="must be a mapping"):
        load_jurisdiction_file(tmp_path / "us.yaml")


def test_generated_from_must_be_mapping(tmp_path: Path) -> None:
    (tmp_path / "us.yaml").write_text(
        f"schema_version: {REGISTRY_SCHEMA_VERSION}\n"
        "jurisdiction: us\n"
        "generated_from: nope\n"
        "concepts: []\n"
    )
    with pytest.raises(ValueError, match="generated_from must be a mapping"):
        load_jurisdiction_file(tmp_path / "us.yaml")


def test_concepts_must_be_list(tmp_path: Path) -> None:
    (tmp_path / "us.yaml").write_text(
        f"schema_version: {REGISTRY_SCHEMA_VERSION}\n"
        "jurisdiction: us\n"
        "concepts: {not: a list}\n"
    )
    with pytest.raises(ValueError, match="concepts must be a list"):
        load_jurisdiction_file(tmp_path / "us.yaml")


def test_concept_missing_required_field_raises(tmp_path: Path) -> None:
    _write(tmp_path, "us.yaml", "- id: us:x#foo\n  kind: output\n")  # no name
    with pytest.raises(ValueError, match="missing 'name'"):
        load_jurisdiction_file(tmp_path / "us.yaml")


def test_concept_must_be_mapping(tmp_path: Path) -> None:
    _write(tmp_path, "us.yaml", "- just-a-string\n")
    with pytest.raises(ValueError, match="each concept must be a mapping"):
        load_jurisdiction_file(tmp_path / "us.yaml")


def test_modules_must_be_list(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "us.yaml",
        "- id: us:x#foo\n  kind: output\n  name: foo\n  modules: {a: b}\n",
    )
    with pytest.raises(ValueError, match="modules must be a list"):
        load_jurisdiction_file(tmp_path / "us.yaml")


def test_modules_scalar_is_coerced(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "us.yaml",
        "- id: us:x#foo\n  kind: output\n  name: foo\n  modules: us:x\n  occurrences: 1\n",
    )
    reg = load_concept_registry(tmp_path)
    foo = reg.get("us:x#foo")
    assert foo is not None and foo.modules == ("us:x",)


def test_mapping_body_must_be_mapping(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "us.yaml",
        """\
- id: us:x#foo
  kind: output
  name: foo
  modules: [us:x]
  occurrences: 1
  mappings:
    policyengine_us: not-a-dict
""",
    )
    with pytest.raises(ValueError, match="mapping for .* must be a mapping"):
        load_jurisdiction_file(tmp_path / "us.yaml")


def test_mappings_must_be_mapping(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "us.yaml",
        """\
- id: us:x#foo
  kind: output
  name: foo
  modules: [us:x]
  occurrences: 1
  mappings: [a, b]
""",
    )
    with pytest.raises(ValueError, match="mappings must be a mapping"):
        load_jurisdiction_file(tmp_path / "us.yaml")


def test_null_mapping_engine_is_skipped(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "us.yaml",
        """\
- id: us:x#foo
  kind: output
  name: foo
  modules: [us:x]
  occurrences: 1
  mappings:
    policyengine_us:
""",
    )
    reg = load_concept_registry(tmp_path)
    foo = reg.get("us:x#foo")
    assert foo is not None and foo.mappings == ()


def test_validate_flags_bad_kind() -> None:
    bad = Concept(id="us:x#foo", kind="sideways", name="foo", modules=("us:x",))
    reg = ConceptRegistry(concepts_by_id={bad.id: bad})
    issues = reg.validate()
    assert any("invalid kind" in i for i in issues)


def test_validate_flags_input_output_marker_mismatch() -> None:
    input_without_marker = Concept(
        id="us:x#foo", kind="input", name="foo", modules=("us:x",)
    )
    output_with_marker = Concept(
        id="us:x#input.bar", kind="output", name="bar", modules=("us:x",)
    )
    reg = ConceptRegistry(
        concepts_by_id={
            input_without_marker.id: input_without_marker,
            output_with_marker.id: output_with_marker,
        }
    )
    issues = reg.validate()
    assert any("missing '#input.' marker" in i for i in issues)
    assert any("carries '#input.' marker" in i for i in issues)


def test_load_raises_on_invalid_registry(tmp_path: Path) -> None:
    # An input id without the marker fails validate() during load.
    _write(
        tmp_path,
        "us.yaml",
        "- id: us:x#foo\n  kind: input\n  name: foo\n  modules: [us:x]\n  occurrences: 1\n",
    )
    with pytest.raises(ValueError, match="Invalid concept registry"):
        load_concept_registry(tmp_path)


def test_concept_mapping_dataclass_defaults() -> None:
    m = ConceptMapping(engine="policyengine_us")
    assert m.mapping_type is None
    assert m.variable is None
