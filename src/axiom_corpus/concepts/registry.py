"""Loader and data structures for the typed concept registry.

The registry is published as one YAML file per jurisdiction under this
package's ``data/`` dir (``us.yaml``, ``us-nc.yaml``, ``uk.yaml``, ...). Each file
carries registry-level provenance (the ``rulespec`` commit scanned, the
PolicyEngine mappings commit imported) plus a flat ``concepts`` list.

The on-disk shape is a deliberate superset of the ``axiom-encode`` concepts
format (``src/axiom_encode/concepts/registry.py``, format
``axiom-encode/concepts/v1``): both use a top-level ``concepts`` list of
mappings with an ``id`` and a name. The encode loader locks one *canonical
name* per legal concept for drift control; this registry instead enumerates
the *actual* input/output name universe with types and cross-engine edges.
Encode's loader is expected to point at this registry as a follow-up (see the
Phase A A3 note); this module does not change encode.

Nothing here binds or enforces the registry. It is a read-only artifact.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Bump when the *file schema* changes shape (fields, nesting). Independent of a
# registry's data version, which tracks content revisions of a given schema.
REGISTRY_SCHEMA_VERSION = "axiom-corpus/concept-registry/v1"

# Directory holding the packaged per-jurisdiction registry files. Lives beside
# this module (``concepts/data``) so it ships as package data and resolves the
# same way for an editable install, a wheel, and the checked-in generator/tests
# — mirroring ``axiom-encode``'s ``concepts/data`` layout.
DEFAULT_DATA_ROOT = Path(__file__).with_name("data")

_VALID_KINDS = frozenset({"input", "output"})


@dataclass(frozen=True)
class ConceptMapping:
    """A cross-engine edge for one concept (e.g. to PolicyEngine-US).

    Fields mirror the source oracle mapping so the edge round-trips without
    loss of the discriminating metadata (``mapping_type``, ``comparison``).
    ``variable`` / ``parameter`` / ``parameter_key`` are mutually informative:
    a ``direct_variable`` mapping carries ``variable``; a ``parameter_value``
    mapping carries ``parameter`` and/or ``parameter_key``.
    """

    engine: str
    mapping_type: str | None = None
    variable: str | None = None
    parameter: str | None = None
    parameter_key: str | None = None
    comparison: str | None = None
    program: str | None = None
    source: str | None = None


@dataclass(frozen=True)
class Concept:
    """One input slot or one rule output in the Axiom name universe.

    ``id`` is the RuleSpec legal id: ``<module_prefix>#<name>`` for outputs and
    ``<module_prefix>#input.<name>`` for inputs. Types are populated only where
    derivable from the defining rule; ``None`` means "not derivable from the
    scanned source", never "guessed default".
    """

    id: str
    kind: str
    name: str
    entity: str | None = None
    dtype: str | None = None
    unit: str | None = None
    period: str | None = None
    modules: tuple[str, ...] = ()
    occurrences: int = 0
    type_ambiguous: bool = False
    mappings: tuple[ConceptMapping, ...] = ()
    source_file: Path | None = None

    @property
    def is_input(self) -> bool:
        return self.kind == "input"

    @property
    def is_output(self) -> bool:
        return self.kind == "output"

    @property
    def is_typed(self) -> bool:
        """True when at least a dtype is known and unambiguous."""
        return self.dtype is not None and not self.type_ambiguous

    def mapping_for(self, engine: str) -> ConceptMapping | None:
        for m in self.mappings:
            if m.engine == engine:
                return m
        return None


@dataclass(frozen=True)
class JurisdictionRegistry:
    """The concepts + provenance from one jurisdiction file."""

    jurisdiction: str
    schema_version: str
    registry_version: str
    generated_from: Mapping[str, Any]
    concepts: tuple[Concept, ...]
    source_file: Path | None = None


@dataclass(frozen=True)
class ConceptRegistry:
    """Resolved registry across all loaded jurisdiction files."""

    jurisdictions: tuple[JurisdictionRegistry, ...] = ()
    concepts_by_id: dict[str, Concept] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.concepts_by_id)

    def get(self, concept_id: str) -> Concept | None:
        return self.concepts_by_id.get(concept_id)

    def inputs(self) -> list[Concept]:
        return [c for c in self.concepts_by_id.values() if c.is_input]

    def outputs(self) -> list[Concept]:
        return [c for c in self.concepts_by_id.values() if c.is_output]

    def with_mapping(self, engine: str) -> list[Concept]:
        return [c for c in self.concepts_by_id.values() if c.mapping_for(engine)]

    def validate(self) -> list[str]:
        """Structural checks. Returns a list of human-readable issues."""
        issues: list[str] = []
        for concept in self.concepts_by_id.values():
            if concept.kind not in _VALID_KINDS:
                issues.append(f"{concept.id}: invalid kind {concept.kind!r}")
            if concept.is_input and "#input." not in concept.id:
                issues.append(f"{concept.id}: input id missing '#input.' marker")
            if concept.is_output and "#input." in concept.id:
                issues.append(f"{concept.id}: output id carries '#input.' marker")
            if concept.occurrences < 0:
                issues.append(f"{concept.id}: negative occurrences")
        return issues


def load_jurisdiction_file(path: Path) -> JurisdictionRegistry:
    """Parse one ``concepts/data/<jurisdiction>.yaml`` file."""
    payload = yaml.safe_load(path.read_text()) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: registry file must be a mapping")

    schema_version = payload.get("schema_version")
    if schema_version != REGISTRY_SCHEMA_VERSION:
        raise ValueError(
            f"{path}: unsupported schema_version {schema_version!r} "
            f"(expected {REGISTRY_SCHEMA_VERSION!r})"
        )

    jurisdiction = str(payload.get("jurisdiction") or path.stem)
    registry_version = str(payload.get("registry_version") or "0")
    generated_from = payload.get("generated_from") or {}
    if not isinstance(generated_from, dict):
        raise ValueError(f"{path}: generated_from must be a mapping")

    raw_concepts = payload.get("concepts") or []
    if not isinstance(raw_concepts, list):
        raise ValueError(f"{path}: concepts must be a list")

    concepts = tuple(
        _concept_from_payload(raw, source_file=path) for raw in raw_concepts
    )
    return JurisdictionRegistry(
        jurisdiction=jurisdiction,
        schema_version=str(schema_version),
        registry_version=registry_version,
        generated_from=generated_from,
        concepts=concepts,
        source_file=path,
    )


def load_concept_registry(data_root: Path | None = None) -> ConceptRegistry:
    """Load every ``*.yaml`` under ``data_root`` (default packaged data).

    Mirrors the ``axiom-encode`` loader's glob-and-merge behaviour so the two
    registries can eventually share a loader. Raises on duplicate concept ids
    across files.
    """
    root = data_root or DEFAULT_DATA_ROOT
    jurisdictions: list[JurisdictionRegistry] = []
    concepts_by_id: dict[str, Concept] = {}

    for path in sorted(root.glob("*.yaml")):
        jr = load_jurisdiction_file(path)
        jurisdictions.append(jr)
        for concept in jr.concepts:
            if concept.id in concepts_by_id:
                prior = concepts_by_id[concept.id].source_file
                raise ValueError(
                    f"Duplicate concept id {concept.id!r} in {prior} and {path}"
                )
            concepts_by_id[concept.id] = concept

    registry = ConceptRegistry(
        jurisdictions=tuple(jurisdictions),
        concepts_by_id=concepts_by_id,
    )
    issues = registry.validate()
    if issues:
        raise ValueError("Invalid concept registry: " + "; ".join(issues))
    return registry


def _concept_from_payload(payload: Any, *, source_file: Path) -> Concept:
    if not isinstance(payload, dict):
        raise ValueError(f"{source_file}: each concept must be a mapping")
    for key in ("id", "kind", "name"):
        if key not in payload:
            raise ValueError(f"{source_file}: concept missing {key!r}: {payload!r}")

    modules_raw = payload.get("modules") or ()
    if isinstance(modules_raw, str):
        modules_raw = (modules_raw,)
    if not isinstance(modules_raw, (list, tuple)):
        raise ValueError(f"{source_file}: modules must be a list")

    return Concept(
        id=str(payload["id"]),
        kind=str(payload["kind"]),
        name=str(payload["name"]),
        entity=_opt_str(payload.get("entity")),
        dtype=_opt_str(payload.get("dtype")),
        unit=_opt_str(payload.get("unit")),
        period=_opt_str(payload.get("period")),
        modules=tuple(str(m) for m in modules_raw),
        occurrences=int(payload.get("occurrences", 0)),
        type_ambiguous=bool(payload.get("type_ambiguous", False)),
        mappings=_mappings_from_payload(payload.get("mappings"), source_file=source_file),
        source_file=source_file,
    )


def _mappings_from_payload(
    payload: Any, *, source_file: Path
) -> tuple[ConceptMapping, ...]:
    if not payload:
        return ()
    if not isinstance(payload, dict):
        raise ValueError(f"{source_file}: mappings must be a mapping keyed by engine")
    out: list[ConceptMapping] = []
    for engine, body in payload.items():
        if body is None:
            continue
        if not isinstance(body, dict):
            raise ValueError(f"{source_file}: mapping for {engine!r} must be a mapping")
        out.append(
            ConceptMapping(
                engine=str(engine),
                mapping_type=_opt_str(body.get("mapping_type")),
                variable=_opt_str(body.get("variable")),
                parameter=_opt_str(body.get("parameter")),
                parameter_key=_opt_str(body.get("parameter_key")),
                comparison=_opt_str(body.get("comparison")),
                program=_opt_str(body.get("program")),
                source=_opt_str(body.get("source")),
            )
        )
    return tuple(out)


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
