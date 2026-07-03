"""Tests for the typed concept registry and its generator.

Two layers of guarantee:

* **Always run**: the checked-in ``concepts/data/*.yaml`` load, parse, and pass
  internal-consistency checks; the embedded ``generated_from`` provenance is
  present; and the loader's structural validation is green. These need no live
  ``rulespec-*`` checkout, so they run in CI.

* **Skip-if-absent**: when the ``rulespec-us`` / ``axiom-encode`` checkouts are
  present next to this repo *and at the exact SHAs embedded in the registry*,
  a fresh regeneration must byte-match the checked-in files. This proves the
  committed registry is the generator's output for its declared input snapshot
  without requiring a live checkout in CI.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from axiom_corpus.concepts import (
    REGISTRY_SCHEMA_VERSION,
    ConceptRegistry,
    load_concept_registry,
    load_jurisdiction_file,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT / "src" / "axiom_corpus" / "concepts" / "data"


@pytest.fixture(scope="module")
def registry() -> ConceptRegistry:
    """Load the checked-in registry once for the whole module (40k concepts)."""
    return load_concept_registry(DATA_ROOT)

# Import the generator module by path (it lives in scripts/, not the package).
_GEN_PATH = REPO_ROOT / "scripts" / "build_concept_registry.py"
_spec = importlib.util.spec_from_file_location("build_concept_registry", _GEN_PATH)
assert _spec and _spec.loader
build_concept_registry = importlib.util.module_from_spec(_spec)
sys.modules["build_concept_registry"] = build_concept_registry
_spec.loader.exec_module(build_concept_registry)


# ---------------------------------------------------------------------------
# Always-run: the checked-in registry is well-formed
# ---------------------------------------------------------------------------


def test_registry_loads(registry: ConceptRegistry) -> None:
    assert len(registry) > 0
    # Federal US must be present and substantial.
    assert any(j.jurisdiction == "us" for j in registry.jurisdictions)


def test_registry_has_us_and_uk(registry: ConceptRegistry) -> None:
    jurs = {j.jurisdiction for j in registry.jurisdictions}
    assert "us" in jurs
    assert "uk" in jurs


def test_every_file_declares_schema_and_provenance() -> None:
    files = sorted(DATA_ROOT.glob("*.yaml"))
    assert files, "no registry files checked in"
    for path in files:
        jr = load_jurisdiction_file(path)
        assert jr.schema_version == REGISTRY_SCHEMA_VERSION
        assert jr.registry_version
        assert jr.generated_from.get("rulespec_sha"), f"{path} missing rulespec_sha"
        assert jr.generated_from.get("rulespec_repo")


def test_internal_consistency(registry: ConceptRegistry) -> None:
    # Loader's validate() runs during load and raises on failure; assert the
    # invariants directly too, so a regression is legible.
    for concept in registry.concepts_by_id.values():
        assert concept.kind in {"input", "output"}
        assert concept.id.count("#") == 1
        prefix, fragment = concept.id.split("#", 1)
        assert ":" in prefix
        if concept.is_input:
            assert fragment.startswith("input.")
            assert concept.name == fragment[len("input.") :]
        else:
            assert not fragment.startswith("input.")
            assert concept.name == fragment
        assert concept.occurrences >= 1
        assert concept.modules


def test_inputs_are_never_type_guessed(registry: ConceptRegistry) -> None:
    """Inputs carry no declared type in source; dtype/unit/period stay unset."""
    for concept in registry.inputs():
        assert concept.dtype is None, f"{concept.id} has guessed dtype"
        assert concept.unit is None, f"{concept.id} has guessed unit"
        assert concept.period is None, f"{concept.id} has guessed period"


def test_outputs_are_mostly_typed(registry: ConceptRegistry) -> None:
    outputs = registry.outputs()
    typed = [c for c in outputs if c.is_typed]
    # RuleSpec rules declare dtype nearly always; guard against a parsing
    # regression that would silently drop types.
    assert len(typed) / len(outputs) > 0.9


def test_pe_mappings_only_on_outputs_and_shaped(registry: ConceptRegistry) -> None:
    mapped = registry.with_mapping("policyengine_us")
    assert mapped, "expected some PolicyEngine-US edges"
    for concept in mapped:
        assert concept.is_output, f"{concept.id}: PE edge on a non-output"
        edge = concept.mapping_for("policyengine_us")
        assert edge is not None
        assert edge.mapping_type is not None
        # A direct_variable edge must name a variable; a parameter_value edge
        # must name a parameter or parameter_key.
        if edge.mapping_type == "direct_variable":
            assert edge.variable, f"{concept.id}: direct_variable without variable"
        if edge.mapping_type == "parameter_value":
            assert edge.parameter or edge.parameter_key, (
                f"{concept.id}: parameter_value without parameter"
            )


def test_no_duplicate_ids_across_files(registry: ConceptRegistry) -> None:
    # load_concept_registry raises on duplicates; this asserts the count math
    # (sum of per-file concepts == merged size) as an independent check.
    total = sum(len(jr.concepts) for jr in registry.jurisdictions)
    assert total == len(registry)


# ---------------------------------------------------------------------------
# Skip-if-absent: fresh regeneration matches the checked-in snapshot
# ---------------------------------------------------------------------------


def _rulespec_root() -> Path:
    return build_concept_registry.default_rulespec_root()


def _checkout_at_embedded_sha(country: str) -> Path | None:
    """Return the rulespec repo path iff it exists at the embedded SHA."""
    repo_name = build_concept_registry.COUNTRY_REPOS.get(country)
    if repo_name is None:
        return None
    repo = _rulespec_root() / repo_name
    if not repo.is_dir():
        return None
    # Find the embedded SHA for this country from any of its files.
    embedded: str | None = None
    for path in DATA_ROOT.glob("*.yaml"):
        jr = load_jurisdiction_file(path)
        if jr.generated_from.get("rulespec_repo") == repo_name:
            embedded = str(jr.generated_from.get("rulespec_sha"))
            break
    if embedded is None:
        return None
    head = build_concept_registry.git_head_sha(repo)
    if head != embedded:
        return None
    return repo


def test_checked_in_matches_generator_when_sources_present() -> None:
    """If rulespec-us is checked out at the embedded SHA, the registry is current."""
    us_repo = _checkout_at_embedded_sha("us")
    if us_repo is None:
        pytest.skip("rulespec-us not present at the embedded snapshot SHA")

    encode_repo = _rulespec_root() / "axiom-encode"
    if not encode_repo.is_dir():
        pytest.skip("axiom-encode not present for PE mapping regeneration")

    # Regenerate only the countries whose checkouts match the snapshot.
    countries = ["us"]
    uk_repo = _checkout_at_embedded_sha("uk")
    if uk_repo is not None:
        countries.append("uk")

    result = build_concept_registry.build(
        _rulespec_root(), encode_repo, countries
    )
    diffs: list[str] = []
    for name, content in result.files.items():
        target = DATA_ROOT / name
        if not target.exists():
            diffs.append(f"missing: {name}")
        elif target.read_text() != content:
            diffs.append(f"stale: {name}")
    assert not diffs, (
        "Checked-in registry differs from a fresh build for the embedded "
        f"snapshot: {diffs}. Run scripts/build_concept_registry.py --write."
    )
