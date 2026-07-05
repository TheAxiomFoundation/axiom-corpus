# Provision anchors — the derived leaf-level annotation layer

Status: **implemented (B3a, 2026-07-04).** Ratified in
[`granularity-policy-proposal.md`](./granularity-policy-proposal.md) §4 ("the
annotation layer is a real table that goes to the drafted leaves").

`corpus.provision_anchors` is a derived, rebuildable table with **one row per
drafted leaf**, keyed by its citation path. It carries char offsets and the
leaf's text into an *asserted* parent provision, so consumers get a corpus that
"really does go to the leaf" everywhere — while `corpus.provisions` keeps
identity anchored to exactly the structure the official source asserts.

## Why a separate layer

`corpus.provisions` stores provisions at the **assertion frontier**: the depth
the publisher actually asserts as identified nodes.

| source | asserts to | example provision |
|---|---|---|
| USLM statutes | paragraph / clause | `us/statute/42/1397aa/a/1` |
| eCFR | the **section** only | `us/regulation/7/273/9` (one row, 56 KB body) |
| manuals / PDFs | block / page | `us-ma/regulation/106-cmr/365/180/A` |

Paragraph hierarchy *inside* a CFR section — `7 CFR 273.9(d)(6)(iii)` — is
indentation typography, not identified nodes. Two reasonable parsers disagree
about where `(d)(6)(iii)` ends, and an upstream typography change can flip the
answer while the law is unchanged. Because a provision's identity is
`uuid5("axiom:" + citation_path)`, baking a parser's guess into the citation
path would make that guess **load-bearing for every grounding, claim, and
staleness pin**.

The asymmetry that decides which layer absorbs sub-frontier structure:

> A wrong **span** is a re-derivation. A wrong **identity** is a migration
> across every consumer.

So asserted structure lives in `corpus.provisions` (identity rows); inferred
structure lives here (re-derivable annotation).

## Schema

`supabase/migrations/20260704120000_corpus_provision_anchors.sql`. Key columns:

- **`citation_path` (PRIMARY KEY)** — the leaf's path, e.g.
  `us/regulation/7/273/9/d/6/iii`. *The path is the stable key.* Paths are
  printed labels; a boundary fix moves offsets, never the key. There is **no
  surrogate row id** — groundings of record cite
  `(parent_provision_id, citation_path, span)`.
- `parent_provision_id` → `corpus.provisions(id)` — the asserted row the span
  indexes into.
- `char_start` / `char_end` — half-open `[start, end)` offsets into the parent
  body.
- `anchor_text` — the leaf text **materialized as a verified-derived column**
  (byte-equal to `parent.body[char_start:char_end]`), so leaf queries, encoder
  prompt slicing, and leaf FTS need no second source of truth.
- `label` — the printed label at the span head, without parens (`d`, `6`,
  `iii`, `A`).
- `confidence` — `machine_asserted` vs `label_inferred` (see below).
- `extractor_version` + `parent_body_sha256` — provenance and the staleness
  guard.

The local artifact form is JSONL under `data/corpus/anchors/`, mirroring the
`data/corpus/provisions/` layout (same relative path as the parent provisions
file).

## Confidence

- **`machine_asserted`** — the span is a pass-through of a boundary the
  publisher already asserts: a deeper provision that exists, or a block leaf the
  source segmented. `us-ma 106 CMR 365.180(A)` is machine_asserted because the
  source stores that block as its own row.
- **`label_inferred`** — the extractor inferred the span from printed-label
  typography. The whole `7 CFR 273.9` paragraph tree is label_inferred because
  eCFR asserts only the section.

## Mechanical gates (enforced at generation and re-verified before load)

Every anchor must pass both, or generation raises rather than emitting a bad
row (`axiom_corpus.corpus.anchors.verify_anchor`):

1. **Byte-equal** — `parent.body[char_start:char_end] == anchor_text`.
2. **Label-at-head** — the printed label `(<label>)` sits at the span head.

`verify_anchors_against_provisions` additionally checks the parent-body hash: if
a parent's body changed since generation, the anchor is rejected as "rebuild
required" rather than silently trusted.

## Rebuild discipline

The table is **derived and rebuildable** from `(provisions × extractor
version)`:

- A boundary correction is a **rebuild** (`generate-anchors` again) plus a
  parent-hash re-check — **never a migration**.
- Bump `EXTRACTOR_VERSION` whenever the algorithm could move offsets; the
  `(parent provision, extractor_version)` pair is the rebuild cache key.
- The committed JSONL is checked in CI to equal the generator's output
  (`test_committed_*_anchors_match_generator`), so a stale artifact fails the
  suite.

## Resolver semantics

`AnchorResolver.resolve(citation_path)` (Python) and
`corpus.resolve_provision_anchor(text)` (SQL RPC) implement the same three-tier
fallback and return `(provision_id, parent_citation_path, span, match_kind)`:

1. **exact** — a leaf whose path equals the query. Preferred.
2. **descendant** — no exact leaf, but the query is an *ancestor* of drafted
   leaves that share one parent provision (e.g. query `.../273/9/d` when only
   `.../d/6/iii` was drafted). Resolves to the minimal span covering all
   matching descendants.
3. **ancestor** — no exact or descendant match, but a *prefix* of the query is a
   drafted leaf (e.g. query `.../d/6/iii/A` drilling below the drafted
   frontier). Resolves to the deepest drafted ancestor's span.

A path matching none of these returns `None` (Python) / zero rows (SQL).

## CLI

```bash
# Generate the derived anchors JSONL from an asserted provisions file.
# --target parses the printed paragraph tree of a section provision;
# --stored-leaf wraps a provision that is already a block leaf.
axiom-corpus-ingest generate-anchors \
  --provisions data/corpus/provisions/us/regulation/2026-05-10-snap-7-cfr-273.jsonl \
  --target us/regulation/7/273/9 \
  --output data/corpus/anchors/us/regulation/2026-05-10-snap-7-cfr-273.jsonl

# Resolve a citation path to (provision_id, span) over an anchors artifact.
axiom-corpus-ingest resolve-anchor \
  --anchors data/corpus/anchors/us/regulation/2026-05-10-snap-7-cfr-273.jsonl \
  us/regulation/7/273/9/d/6/iii

# Optional: upsert an anchors artifact into corpus.provision_anchors.
axiom-corpus-ingest load-anchors-supabase \
  --anchors data/corpus/anchors/us/regulation/2026-05-10-snap-7-cfr-273.jsonl \
  --provisions data/corpus/provisions/us/regulation/2026-05-10-snap-7-cfr-273.jsonl
```

## Populated targets (issue-14)

- **`7 CFR 273.9`** — the paragraph tree is parsed from the stored section
  provision (`us/regulation/7/273/9`, one row) down to drafted leaves.
  `us/regulation/7/273/9/d/6/iii` ("Standard utility allowances") is
  addressable — the exact subsection the 7 SNAP specs and rulespec-us #440
  reference.
- **`us-ma 106 CMR 365.180`** — the stored block leaf
  `us-ma/regulation/106-cmr/365/180/A` is anchored `machine_asserted`, plus its
  run-in numbered children `.../A/1`, `.../A/2`, `.../A/3` as `label_inferred`.
  So `…/365/180/A` resolves. See the PR body for how this retires the two us-ma
  entries in `rulespec-us/known-dangling.yaml` (follow-up work lives in
  rulespec-us; this repo stays additive).
