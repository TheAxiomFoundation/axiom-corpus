"""Typed concept registry for the Axiom stack.

The concept registry is the versioned vocabulary of input and output *names*
that the Axiom rules stack uses. Each concept is one input slot or one rule
output, identified by its RuleSpec legal id (``us:statutes/7/2014/d#foo``),
typed where the type is derivable from the defining rule, and annotated with
cross-engine mapping edges (currently PolicyEngine-US).

This package is a read-only published artifact seeded in Phase A of the Axiom
rebuild plan (item A3). Nothing binds to or enforces it yet; it exists so that
downstream automation (oracle mapping, microsim projections, test-input
defaults) has a single machine-readable name universe to build on.

See ``docs/concept-registry.md`` for the format and rationale.
"""

from __future__ import annotations

from axiom_corpus.concepts.registry import (
    REGISTRY_SCHEMA_VERSION,
    Concept,
    ConceptMapping,
    ConceptRegistry,
    JurisdictionRegistry,
    load_concept_registry,
    load_jurisdiction_file,
)

__all__ = [
    "REGISTRY_SCHEMA_VERSION",
    "Concept",
    "ConceptMapping",
    "ConceptRegistry",
    "JurisdictionRegistry",
    "load_concept_registry",
    "load_jurisdiction_file",
]
