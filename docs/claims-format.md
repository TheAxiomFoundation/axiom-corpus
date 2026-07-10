# Source claims format

Source claims are thin, reviewed, evidence-backed assertions about what a
corpus source span *says* or how one source relates to another. They live in
`claims/**/*.jsonl` (one JSON object per line) and are consumed by
[`axiom-encode`](https://github.com/TheAxiomFoundation/axiom-encode)'s proof
validator as one of three ways an executable RuleSpec atom can be grounded
(direct source text, an accepted claim, or an imported RuleSpec export).

Claims are **non-executable**: they may assert `sets`, `defines`, `amends`,
`implements`, `restates`, `delegates`, `applies_to`, `requires`,
`supersedes`, and `creates_exception`, but must never carry formulas, case
inputs, outputs, tests, traces, decisions, or benefit amounts.

See also `axiom-encode/docs/rulespec-proof-validation.md` for the validator
side of this contract.

## The compatibility surface (do not break)

Two fields form the interface that `axiom-encode` keys on. Changing either is a
coordinated cross-repo change, never a corpus-only edit:

- **`id`** — the claim's stable primary key. `rulespec-*` modules reference
  claims by this id in `module.source_claims`, and the proof validator resolves
  those ids against the files here. Renaming an `id` silently breaks every
  module that cites it.
- **`subject`** — must be an **absolute** legal, corpus, or RuleSpec target
  (e.g. `us:statutes/7/2014/e`, or a rule-slot target such as
  `us:statutes/7/2017/a#snap_allotment_before_minimum.input.snap_maximum_allotment`).
  The validator (`find_source_claim_reference_issues` →
  `_validate_source_claim_subject`) **explicitly rejects** friendly concept
  ids (`snap.maximum_allotment`) and any `subject.type == "concept"`.

The validator also scans the *entire* claim record for execution-reserved keys
(`formula`, `input(s)`, `output(s)`, `case(s)`, `test(s)`, `result(s)`,
`eligibility`, `benefit_amount`, `decision`, `runtime`, `trace(s)`). Any new
field must avoid those names anywhere in the record.

## Current record shape

```jsonc
{
  "id": "claims:us/guidance/usda/fns/snap-fy2026-cola/page-1#sets-maximum-allotments",
  "kind": "sets",
  "status": "accepted",
  "subject": {                       // absolute target — the primary key surface
    "type": "statutory_rule_slot",
    "id": "us:statutes/7/2017/a#snap_allotment_before_minimum.input.snap_maximum_allotment",
    "statutory_reference": "7 USC 2017(a)",
    "corpus_citation_path": "us/statute/7/2017",
    "rulespec_id": "us:statutes/7/2017/a#snap_allotment_before_minimum",
    "slot": "snap_maximum_allotment",
    "label": "maximum allotment input to the regular SNAP allotment formula"
  },
  "object": { "type": "parameter_table", "unit": "USD", "period": "Month",
              "indexed_by": ["household_size", "snap_region"],
              "effective_from": "2025-10-01", "effective_to": "2026-09-30" },
  "concept": { /* additive — see below */ },
  "evidence": [
    {
      "corpus_citation_path": "us/guidance/usda/fns/snap-fy2026-cola/page-1",
      "selector": { "type": "text_contains",
                    "text": "Maximum Allotments Table 1: Maximum Monthly Allotment" },
      "span": { /* additive — see below */ },
      "quote": "Maximum Allotments Table 1: Maximum Monthly Allotment"
    }
  ],
  "provenance": { "method": "manual", "reviewer": "codex", "reviewed_at": "2026-05-03" }
}
```

## Additive fields (Phase A, item A4)

A4 makes the claims layer survive rule renames by grounding claims in two ways
that do **not** depend on any rulespec identifier. Both fields are strictly
additive — `id`, `subject`, `object`, and the existing evidence fields are left
byte-for-byte unchanged — so the live proof-validation gate is unaffected.
`tests/test_claims.py::test_additive_fields_do_not_disturb_the_validator_contract`
asserts these invariants structurally.

### `concept` — concept-registry cross-reference

Cross-references the typed concept registry
(`src/axiom_corpus/concepts/`, schema `axiom-corpus/concept-registry/v1`,
seeded in Phase A item A3). It records *which registry concepts* the claim's
`sets` object populates, so that when a rulespec module or slot is renamed the
claim still points at a stable name in the registry vocabulary.

```jsonc
"concept": {
  "scheme": "axiom-corpus/concept-registry/v1",
  "registry_version": "0.1.0",
  "jurisdiction_file": "us.yaml",
  "module": "us:policies/usda/snap/fy-2026-cola/maximum-allotments",
  "anchor_concept_ids": [
    "us:policies/usda/snap/fy-2026-cola/maximum-allotments#snap_maximum_allotment"
  ],
  "note": "Cross-reference into the concept registry (PR #171). Resolution is advisory; the claim subject remains the primary key consumed by axiom-encode's proof validator."
}
```

- `module` resolves to a registry concept module (an id prefix / `modules[]`
  entry); `anchor_concept_ids` are specific registry concept ids the claim's
  `sets` object directly establishes.
- Resolution is **advisory today**: nothing binds to it, and the claim
  `subject` remains the sole key the validator consumes.
- `tests/test_claims.py::test_every_concept_cross_reference_resolves_in_registry`
  loads the registry (via `axiom_corpus.concepts.load_concept_registry`, or the
  packaged YAML) and asserts every `module` and `anchor_concept_ids` entry
  resolves. It **skips** cleanly when the registry package is absent, so this
  data can land before, or alongside, PR #171.

### `span` — release-pinned span anchor (per evidence item)

Converts the `text_contains` selector into a verified char-offset anchor
against a named corpus release, so the grounding is pinned to source geometry
rather than to a fragile substring search at encode time. `text_contains`
(and `quote`) are **preserved** alongside.

```jsonc
"span": {
  "release": "r0",
  "provision_citation_path": "us/guidance/usda/fns/snap-fy2026-cola/page-1",
  "char_start": 258,
  "char_end": 311,
  "sha256_of_provision_text": "806907224a37eecb7fb5fa3f8279fcd7bd29de7bd3fc9c3111953d2cb6701566"
}
```

- `release` is the historical claim-anchor label for the corpus text against
  which the offsets were calculated. It is not an immutable v2 corpus release
  identity. Existing `r0` spans must migrate to their own release-scoped,
  signed claims contract before production use.
- `char_start`/`char_end` index into the provision `body` for
  `provision_citation_path`; the slice must equal the selector text.
- `sha256_of_provision_text` is the SHA-256 of the *entire* provision body, so
  a re-extraction can prove it is reading the same source bytes the anchor was
  built against.
- `tests/test_claims.py::test_every_evidence_span_reextracts_to_its_selector`
  re-reads the provision JSONL, re-slices each span, and asserts it equals the
  selector text and that the body hash matches. This is the guarantee that a
  rule rename can never silently orphan a claim's evidence.

Claims are not part of an immutable corpus release object. Corpus release
objects contain only selected source-first artifacts and their validation
attestations; claims and downstream waivers require their own signed boundary.

## The future flip (explicitly deferred, coordinated change)

The long-term A4 target (architecture review finding 3; rebuild plan A4) is to
**re-key claim subjects to registry concept ids** — demoting today's rulespec
module/slot ids to annotations — so a claim is grounded in the concept
vocabulary rather than in a specific encoding's slot names. That is deliberately
**not** done here, because it would break the live gate: `axiom-encode`'s
`_validate_source_claim_subject` currently *rejects* concept-style subjects, and
`rulespec-*` modules resolve claims by today's `id`.

The flip requires a coordinated change across repos, landed in this order:

1. **axiom-encode** teaches `_validate_source_claim_subject` (and the docs in
   `rulespec-proof-validation.md`) to accept absolute registry concept ids as
   valid subjects — additively, so both forms validate during migration.
2. **Concept registry** (this repo, A3) is stable and versioned enough that a
   subject can pin `(scheme, registry_version, concept_id)`.
3. **Claims** gain concept-keyed subjects (or a `subject.concept` alongside the
   legal target) without dropping the legal/corpus target the validator and the
   `module.source_claims` allowlist still consume.
4. **rulespec-*** module `source_claims` references are unaffected (they key on
   `id`, which does not change), but any tooling that reads `subject` learns the
   new shape.

Until all four are in place, subjects stay as absolute legal/corpus/RuleSpec
targets and the concept relationship is expressed only through the additive
`concept` cross-reference above.
