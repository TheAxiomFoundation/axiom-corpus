from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLAIMS_ROOT = ROOT / "claims"
PROVISIONS_ROOT = ROOT / "data" / "corpus" / "provisions"
FRIENDLY_CONCEPT_ID = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
ABSOLUTE_TARGET_ID = re.compile(r"^[a-z][a-z0-9_.-]*:[^\s]+$")

# The additive A4 fields cross-reference release r0 (PR #170) and the concept
# registry schema (PR #171). Kept as constants so a release/schema bump is a
# one-line change with a failing test if a claim lags behind.
SPAN_RELEASE = "r0"
CONCEPT_REGISTRY_SCHEME = "axiom-corpus/concept-registry/v1"


def iter_claim_records() -> list[tuple[Path, int, dict[str, Any]]]:
    records: list[tuple[Path, int, dict[str, Any]]] = []
    if not CLAIMS_ROOT.exists():
        return records

    for path in sorted(CLAIMS_ROOT.rglob("*.jsonl")):
        for line_number, line in enumerate(path.read_text().splitlines(), start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            assert isinstance(payload, dict)
            records.append((path, line_number, payload))
    return records


def _load_provision_bodies() -> dict[str, str]:
    """Map every provision ``citation_path`` to its verbatim ``body`` text.

    Reads the corpus provision JSONL directly so the test has no runtime
    dependency beyond the repo's own release-r0 artifacts.
    """
    bodies: dict[str, str] = {}
    if not PROVISIONS_ROOT.exists():
        return bodies
    for path in sorted(PROVISIONS_ROOT.rglob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                continue
            citation_path = record.get("citation_path")
            body = record.get("body")
            if isinstance(citation_path, str) and isinstance(body, str) and body:
                bodies[citation_path] = body
    return bodies


def _iter_evidence(
    claim: dict[str, Any],
) -> list[dict[str, Any]]:
    evidence = claim.get("evidence")
    return [item for item in evidence if isinstance(item, dict)] if isinstance(
        evidence, list
    ) else []


def test_claim_subjects_use_legal_or_rulespec_pointers() -> None:
    invalid: list[str] = []

    for path, line_number, claim in iter_claim_records():
        subject = claim.get("subject")
        if not isinstance(subject, dict):
            invalid.append(f"{path.relative_to(ROOT)}:{line_number}: missing subject")
            continue

        subject_type = str(subject.get("type") or "")
        subject_id = str(subject.get("id") or "")
        if not ABSOLUTE_TARGET_ID.match(subject_id):
            invalid.append(
                f"{path.relative_to(ROOT)}:{line_number}: non-absolute subject id `{subject_id}`"
            )
        if subject_type == "concept":
            invalid.append(
                f"{path.relative_to(ROOT)}:{line_number}: concept subject `{subject_id}`"
            )
        if FRIENDLY_CONCEPT_ID.match(subject_id):
            invalid.append(
                f"{path.relative_to(ROOT)}:{line_number}: friendly subject id `{subject_id}`"
            )

    assert invalid == []


def test_every_evidence_span_reextracts_to_its_selector() -> None:
    """Every claim evidence item carries a span anchor that re-extracts exactly.

    For each evidence item the span's ``[char_start:char_end]`` slice of the
    cited provision body must equal the ``text_contains`` selector text, and the
    recorded ``sha256_of_provision_text`` must match the full provision body.
    This is the guarantee that makes the claims layer survive rule renames: the
    grounding is pinned to source char offsets under a named release, not to any
    rulespec identifier.
    """
    bodies = _load_provision_bodies()
    records = iter_claim_records()
    assert records, "expected at least one claim record"

    checked = 0
    problems: list[str] = []
    for path, line_number, claim in records:
        rel = f"{path.relative_to(ROOT)}:{line_number}"
        for index, evidence in enumerate(_iter_evidence(claim)):
            selector = evidence.get("selector")
            selector_text = (
                str(selector.get("text") or "")
                if isinstance(selector, dict)
                else ""
            )
            span = evidence.get("span")
            if not isinstance(span, dict):
                problems.append(f"{rel} evidence[{index}]: missing `span` anchor")
                continue

            if span.get("release") != SPAN_RELEASE:
                problems.append(
                    f"{rel} evidence[{index}]: span.release "
                    f"`{span.get('release')}` != `{SPAN_RELEASE}`"
                )

            citation_path = str(span.get("provision_citation_path") or "")
            evidence_path = str(evidence.get("corpus_citation_path") or "")
            if citation_path != evidence_path:
                problems.append(
                    f"{rel} evidence[{index}]: span.provision_citation_path "
                    f"`{citation_path}` != evidence.corpus_citation_path "
                    f"`{evidence_path}`"
                )

            body = bodies.get(citation_path)
            if body is None:
                problems.append(
                    f"{rel} evidence[{index}]: no provision body for "
                    f"`{citation_path}` (release {SPAN_RELEASE})"
                )
                continue

            char_start = span.get("char_start")
            char_end = span.get("char_end")
            if not isinstance(char_start, int) or not isinstance(char_end, int):
                problems.append(
                    f"{rel} evidence[{index}]: char_start/char_end must be ints"
                )
                continue

            extracted = body[char_start:char_end]
            if extracted != selector_text:
                problems.append(
                    f"{rel} evidence[{index}]: span slice "
                    f"[{char_start}:{char_end}] does not re-extract to the "
                    f"selector text ({extracted!r} != {selector_text!r})"
                )

            expected_hash = str(span.get("sha256_of_provision_text") or "")
            actual_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
            if expected_hash != actual_hash:
                problems.append(
                    f"{rel} evidence[{index}]: sha256_of_provision_text "
                    f"`{expected_hash[:12]}...` != actual "
                    f"`{actual_hash[:12]}...`"
                )
            checked += 1

    assert problems == [], "span-anchor verification failures:\n" + "\n".join(problems)
    assert checked > 0, "no evidence spans were checked"


def _load_concept_registry_ids() -> set[str] | None:
    """Resolve the concept id/module universe from the registry (PR #171).

    Returns ``None`` — signalling the caller to skip — when the concept
    registry package is not present in this checkout (i.e. PR #171 has not
    merged and this branch was not based on it). When present, we prefer the
    package's own loader; if only the packaged data files exist we parse them
    directly so the check does not depend on import side effects.
    """
    try:
        from axiom_corpus.concepts import load_concept_registry
    except Exception:
        load_concept_registry = None  # type: ignore[assignment]

    if load_concept_registry is not None:
        try:
            registry = load_concept_registry()
        except Exception:
            registry = None
        if registry is not None and len(registry) > 0:
            ids: set[str] = set()
            for concept in registry.concepts_by_id.values():
                ids.add(concept.id)
                ids.add(concept.id.split("#", 1)[0])
                for module in concept.modules:
                    ids.add(module)
            return ids

    # Fallback: parse the packaged per-jurisdiction YAML directly.
    data_root = ROOT / "src" / "axiom_corpus" / "concepts" / "data"
    if not data_root.is_dir():
        return None
    try:
        import yaml
    except Exception:
        return None
    ids = set()
    found_any = False
    for path in sorted(data_root.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for concept in payload.get("concepts") or []:
            if not isinstance(concept, dict):
                continue
            concept_id = str(concept.get("id") or "")
            if not concept_id:
                continue
            found_any = True
            ids.add(concept_id)
            ids.add(concept_id.split("#", 1)[0])
            modules = concept.get("modules") or []
            if isinstance(modules, str):
                modules = [modules]
            for module in modules:
                ids.add(str(module))
    return ids if found_any else None


def test_every_concept_cross_reference_resolves_in_registry() -> None:
    """Every claim ``concept`` cross-reference resolves in the concept registry.

    The claim's ``concept.module`` must resolve to a registry concept module,
    and every ``concept.anchor_concept_ids`` entry must resolve to a registry
    concept id. Skips cleanly when the registry package (PR #171) is absent so
    this branch stays independently mergeable; runs and passes once #171 lands.
    """
    registry_ids = _load_concept_registry_ids()
    if registry_ids is None:
        pytest.skip(
            "concept registry (PR #171 / axiom_corpus.concepts) not present in "
            "this checkout; concept cross-references verified out-of-band"
        )

    records = iter_claim_records()
    problems: list[str] = []
    checked_modules = 0
    checked_concepts = 0
    for path, line_number, claim in records:
        rel = f"{path.relative_to(ROOT)}:{line_number}"
        concept = claim.get("concept")
        if not isinstance(concept, dict):
            problems.append(f"{rel}: missing `concept` cross-reference")
            continue

        if concept.get("scheme") != CONCEPT_REGISTRY_SCHEME:
            problems.append(
                f"{rel}: concept.scheme `{concept.get('scheme')}` != "
                f"`{CONCEPT_REGISTRY_SCHEME}`"
            )

        module = str(concept.get("module") or "")
        if not module:
            problems.append(f"{rel}: concept.module is empty")
        elif module not in registry_ids:
            problems.append(f"{rel}: concept.module `{module}` not in registry")
        else:
            checked_modules += 1

        anchors = concept.get("anchor_concept_ids")
        if not isinstance(anchors, list) or not anchors:
            problems.append(f"{rel}: concept.anchor_concept_ids must be non-empty")
            continue
        for anchor in anchors:
            anchor_id = str(anchor)
            if anchor_id not in registry_ids:
                problems.append(
                    f"{rel}: anchor concept id `{anchor_id}` not in registry"
                )
            else:
                checked_concepts += 1

    assert problems == [], "concept-resolution failures:\n" + "\n".join(problems)
    assert checked_modules > 0 and checked_concepts > 0, (
        "no concept cross-references were checked"
    )


def test_additive_fields_do_not_disturb_the_validator_contract() -> None:
    """The A4 fields are additive: they never touch the compatibility surface.

    axiom-encode's proof validator keys on the claim ``id`` (from
    ``module.source_claims``) and rejects friendly-concept *subjects*. The A4
    enrichment must therefore keep ``id`` and ``subject`` as the untouched
    primary key, and must not introduce any key that the validator's
    executable-field scan would reject. This test asserts those invariants
    structurally so a future edit that, say, moves a registry id into
    ``subject`` fails here before it can break the live gate.
    """
    # Mirror of axiom-encode's _SOURCE_CLAIM_EXECUTABLE_KEYS. Keeping a copy
    # here means a rename that would trip the real scan fails in-repo first.
    executable_keys = {
        "formula",
        "formulas",
        "input",
        "inputs",
        "output",
        "outputs",
        "case",
        "cases",
        "test",
        "tests",
        "test_cases",
        "runtime",
        "trace",
        "traces",
        "result",
        "results",
        "eligibility",
        "benefit_amount",
        "decision",
    }

    def walk_keys(value: Any) -> list[str]:
        keys: list[str] = []
        if isinstance(value, dict):
            for key, child in value.items():
                keys.append(str(key))
                keys.extend(walk_keys(child))
        elif isinstance(value, list):
            for child in value:
                keys.extend(walk_keys(child))
        return keys

    problems: list[str] = []
    for path, line_number, claim in iter_claim_records():
        rel = f"{path.relative_to(ROOT)}:{line_number}"

        subject = claim.get("subject")
        if not isinstance(subject, dict) or not str(subject.get("id") or ""):
            problems.append(f"{rel}: subject.id is the primary key and must exist")
        else:
            # The subject id must be an absolute target, never a friendly
            # concept id — the concept cross-reference lives in `concept`, not
            # `subject`.
            subject_id = str(subject["id"])
            if FRIENDLY_CONCEPT_ID.match(subject_id) or subject.get("type") == "concept":
                problems.append(
                    f"{rel}: subject must not be a friendly concept id "
                    f"(`{subject_id}`); use the `concept` field instead"
                )

        offending = sorted(
            {key for key in walk_keys(claim) if key in executable_keys}
        )
        if offending:
            problems.append(
                f"{rel}: record contains validator-reserved executable keys "
                f"{offending}"
            )

    assert problems == [], "additive-field contract failures:\n" + "\n".join(problems)
