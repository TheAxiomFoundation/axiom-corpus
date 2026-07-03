# Concept registry

The concept registry is the versioned vocabulary of **input and output names**
the Axiom rules stack uses. It is a read-only, machine-readable artifact seeded
in Phase A of the Axiom rebuild plan (item A3). Nothing binds to or enforces it
yet — it exists so downstream automation has one place to look up the name
universe, its types, and its cross-engine edges.

## What is a concept

One concept is either:

- an **output** — a `rules[].name` produced by a RuleSpec module, identified by
  its legal id `<jurisdiction>:<module-path>#<name>`
  (e.g. `us:statutes/7/2014/d#student_child_income_age_limit`); or
- an **input** — a slot a module consumes, identified by
  `<jurisdiction>:<module-path>#input.<name>`
  (e.g. `us:statutes/7/2014/d#input.person_age`).

Inputs and outputs are distinct concepts even when the bare name coincides;
their legal ids differ by the `#input.` marker.

## Files and layout

The registry is published as one YAML file per jurisdiction under
`src/axiom_corpus/concepts/data/`:

```
src/axiom_corpus/concepts/data/us.yaml          # US federal
src/axiom_corpus/concepts/data/us-ca.yaml       # California
src/axiom_corpus/concepts/data/uk.yaml          # UK
...
```

Each file carries registry-level provenance and a flat `concepts` list:

```yaml
schema_version: axiom-corpus/concept-registry/v1
registry_version: 0.1.0
jurisdiction: us
generated_from:
  rulespec_repo: rulespec-us
  rulespec_sha: f286f811dc9aea118a106f5817032992e294461d
  module_count: 606
  policyengine_mappings_repo: axiom-encode
  policyengine_mappings_path: src/axiom_encode/oracles/policyengine/mappings/us.yaml
  policyengine_mappings_sha: e26ebc49bbc9693a1411e61dca1fc6377e184953
concept_count: 7113
input_count: 4473
output_count: 2640
concepts:
  - id: us:statutes/7/2014/d#student_child_income_age_limit
    kind: output
    name: student_child_income_age_limit
    dtype: Integer
    modules: [us:statutes/7/2014/d]
    occurrences: 1
  - id: us:statutes/42/1396a/a/10#is_medicaid_eligible
    kind: output
    name: is_medicaid_eligible
    entity: Person
    dtype: Judgment
    period: Month
    modules: [us:statutes/42/1396a/a/10]
    occurrences: 1
    mappings:
      policyengine_us:
        mapping_type: direct_variable
        variable: is_medicaid_eligible
  - id: us:statutes/7/2014/d#input.person_age
    kind: input
    name: person_age
    modules: [us:statutes/7/2014/d]
    occurrences: 1
```

### Concept fields

| field | meaning |
|---|---|
| `id` | RuleSpec legal id; the concept's stable identity |
| `kind` | `input` or `output` |
| `name` | the bare slot/output name (the id fragment after `#`, minus `input.`) |
| `entity` | RuleSpec entity (`Household`, `Person`, `TaxUnit`, …) where derivable |
| `dtype` | RuleSpec dtype (`Money`, `Integer`, `Judgment`, `Rate`, …) where derivable |
| `unit` | e.g. `USD` where derivable |
| `period` | `Day` / `Week` / `Month` / `Year` where derivable |
| `type_ambiguous` | `true` when defining rules disagree on a type field (the field is then omitted, never guessed) |
| `modules` | defining/consuming module path(s) |
| `occurrences` | how many rules define (outputs) or reference (inputs) the concept |
| `mappings` | cross-engine edges, keyed by engine (currently `policyengine_us`) |

### Typing policy

Types are populated **only where derivable from the source**, never guessed:

- **Outputs** inherit `entity` / `dtype` / `unit` / `period` from the defining
  rule's declared fields. When the same output name is defined by rules that
  disagree on a field, that field is dropped and `type_ambiguous: true` is set.
- **Inputs** carry no declared type in RuleSpec (they are referenced by tests
  and formulas, not declared). So `dtype` / `unit` / `period` are always unset
  for inputs. `entity` is set only when **every** rule in the consuming module
  agrees on one entity — the single unambiguous signal — and left unset
  otherwise.

A `None`/absent type means "not derivable from the scanned source", not "no
type". Binding a type onto an input is deliberately deferred (see out of scope).

## Cross-engine mappings

`mappings.policyengine_us` imports the PolicyEngine-US oracle mappings from
`axiom-encode` (`src/axiom_encode/oracles/policyengine/mappings/us.yaml`) onto
matching output ids. The edge preserves the discriminating metadata:

- `mapping_type` — `direct_variable`, `parameter_value`, or `not_comparable`;
- `variable` — the PolicyEngine variable (`direct_variable` edges);
- `parameter` / `parameter_key` — the PolicyEngine parameter (`parameter_value`);
- `comparison`, `program` — carried through for downstream use.

These are seed edges: they let oracle-mapping automation start from the existing
hand-curated correspondence instead of a blank slate.

## Regenerating

The registry is generated, not hand-edited. Regenerate from local `rulespec-*`
checkouts:

```bash
# Dry run (prints a per-jurisdiction summary):
uv run python scripts/build_concept_registry.py

# Write src/axiom_corpus/concepts/data/*.yaml:
uv run python scripts/build_concept_registry.py --write

# CI-style consistency check (fails if checked-in files are stale):
uv run python scripts/build_concept_registry.py --check
```

The generator is deterministic: given the same input checkouts, it writes
byte-identical files (sorted ids, stable field order). It auto-discovers the
directory holding `rulespec-us` (a sibling clone, or `../..` in a worktree);
override with `--rulespec-root` / `--encode-repo`.

### Snapshot consistency test

`tests/test_concept_registry.py` guarantees two things:

1. **Always** (no checkout needed, runs in CI): the checked-in files load,
   parse, and pass internal-consistency checks; provenance is present; PE edges
   are shaped correctly; inputs are never type-guessed.
2. **Skip-if-absent**: when `rulespec-us` (and optionally `rulespec-uk`) are
   checked out **at the exact SHA embedded in `generated_from.rulespec_sha`**, a
   fresh regeneration must byte-match the committed files. This proves the
   registry is current for its declared input snapshot without requiring a live
   rules checkout in CI. When the checkout is absent or at a different SHA, the
   test skips.

## What this unlocks

- **Oracle mapping automation** — a typed output universe with seed PE edges is
  the substrate for suggesting and validating new oracle correspondences instead
  of hand-curating each one.
- **Microsim projections** — the input universe (with entities where known) is
  the list of variables a population dataset must supply to run a module.
- **Test-input defaults** — a canonical input set per module supports generating
  or checking companion-test fixtures.
- **Name-stability tracking** — a versioned name universe is the diff baseline
  for the rebuild plan's name-stability contract (invariant 6) and for the
  planned claims re-keying (A4).

## Out of scope for the seed

This is a **read-only artifact**. Deliberately **not** in this seed:

- **Binding / enforcement.** Nothing consumes the registry as a constraint yet.
  The `axiom-encode` concepts loader
  (`src/axiom_encode/concepts/registry.py`) is expected to point at this
  registry as a follow-up; that change is not made here.
- **Canonical-name resolution / synonym blocking.** The encode registry locks
  one canonical name per legal concept for drift control; this registry
  enumerates the *actual* names in use. Reconciling the two is future work.
- **Input type inference beyond entity-agreement.** Assigning `dtype` to inputs
  requires dataflow analysis (which rule field an input flows into) that is not
  attempted here.
- **Cross-jurisdiction concept identity.** Each jurisdiction's names stand on
  their own; unifying, say, a federal and a state "gross income" concept is not
  modeled.

The on-disk shape is a deliberate superset of the `axiom-encode`
`axiom-encode/concepts/v1` format (both are a top-level `concepts` list of
mappings with `id` + name), so the encode loader can adopt this registry with a
thin adapter rather than a parallel format.
