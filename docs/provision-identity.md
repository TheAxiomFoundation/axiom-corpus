# Provision identity and path-mapping events

Companion to [`schema/citation-path.v1.md`](../schema/citation-path.v1.md).
Phase-A item **A6** (`axiom-rebuild-plan-2026-07-02.md`), and the disposition of
architecture-review finding #4: *"Provision ID = uuid5(citation_path);
re-segmentation dangles everything."*

## 1. Provision IDs are a pure function of the citation path

A corpus provision's `id` is not random and is not assigned by the database. It
is derived deterministically from the citation path via `uuid5`, in one of two
forms, both defined in code:

```python
# src/axiom_corpus/ingest/supabase.py  (_deterministic_id)
# src/axiom_corpus/corpus/supabase.py  (deterministic_provision_id, no version)
uuid5(NAMESPACE_URL, f"axiom:{citation_path}")

# src/axiom_corpus/corpus/supabase.py  (deterministic_provision_id, with version)
uuid5(NAMESPACE_URL, json.dumps(["axiom", version, citation_path], separators=(",", ":")))
```

The path-only form is the historical identity; the versioned form was added so
one citation can coexist across staged/published release versions. Verified
against r0: **51,404 / 51,428 stored IDs (99.95%)** reproduce from one of these
two forms against the current path.

## 2. Therefore: path identity IS provision identity

Because `id = f(citation_path)`, **changing a path is not an edit — it is a
delete-plus-create.** The old path's UUID ceases to exist; a new UUID appears.
This is the single most important operational fact about the corpus, and
everything that references a provision by identity dangles when a path moves:

- `rulespec` modules via `module.source_verification.corpus_citation_path`;
- claim subjects (A4);
- the `provisions_to_rules` reverse index (`rulespec-us#523`) — keyed on the
  corpus citation path;
- any span/subpath **anchor** into a provision.

A re-segmentation done without a migration record silently orphans all of the
above. That is the failure this note and the grammar exist to prevent.

## 3. Identity drift already present at r0

The grammar validator
([`scripts/validate_citation_paths.py`](../scripts/validate_citation_paths.py))
tracks **identity drift**: provisions whose stored `id` reproduces from *neither*
identity form, meaning the path was edited after the UUID was minted. At r0 there
are **21** such paths (baseline list in
`schema/citation-path.v1.json` → `identity_drift_ratchet.baseline_paths`):

| cluster | count | note |
|---|---|---|
| `us/regulation/42/435/550`…`563` | 14 | CMS Medicaid community-engagement (42 CFR 435), re-segmented after ingest |
| `us-ny/policy/otda/tanf-state-plan-2024-2026/…` | 4 | NY TANF state plan |
| `us-ma/…` (`106-cmr/365/180/A`, DTA SNAP-COLA SUA) | 3 | same drift that surfaces as dangling scope entries in `axiom-programs#14` |

The validator **fails if this set grows**. Remediation for an existing entry:
re-ingest the provision so its UUID matches the current path again, and emit the
§4 events so consumers migrate. These are tracked debt, not accepted state.

## 4. Path-mapping event vocabulary (specification only)

Any future release that changes paths **must** emit a machine-readable
path-mapping stream so consumers migrate deterministically. This note and
`schema/citation-path.v1.md` §6 specify the vocabulary; **no implementation
ships in this PR** (it is additive-only). The full event shape and the
`path-mapping/<version>.jsonl` location are in the schema doc. Summary:

| `type` | old → new | content-preserving? |
|---|---|---|
| `rename` | 1 → 1 | yes (re-point mechanically) |
| `move` | 1 subtree → 1 subtree | yes |
| `split` | 1 → N | **no** — regrounded content must be re-reviewed |
| `merge` | N → 1 | **no** |
| `retire` | 1 → 0 | must dangle loudly |
| `introduce` | 0 → 1 | n/a |

Each event carries both the old and new `citation_path` and the corresponding
`provision_id` (computed with the §1 formula), so a consumer can replay the
mapping against its own by-UUID references. The stream is append-only and part
of the signed corpus release manifest (A2).

## 5. Practical rules for contributors

1. **Never rename a path in place** as a "cleanup." It re-mints the UUID and
   dangles every consumer. If a path is wrong, treat it as a `rename`/`split`
   event with a migration record.
2. **Prefer additive segmentation.** Adding a new leaf is an `introduce`;
   re-segmenting an existing leaf is a `split` and invalidates its dependents.
3. **When you must re-segment,** run `validate_citation_paths.py`, confirm the
   drift set did not grow unexpectedly, and pair the change with the event
   stream and a rulespec `corpus_citation_path` migration.
4. The grammar validator is the guardrail: it runs in CI (this PR wires it) and
   turns a silent identity break into a red build.
