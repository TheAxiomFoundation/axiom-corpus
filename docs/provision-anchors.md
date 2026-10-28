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
answer while the law is unchanged. Because a provision's identity derives from
its citation path (`uuid5("axiom:" + citation_path)`; when staging, Supabase
replaces that id with one that also folds in the version), baking a parser's
guess into the citation path would make that guess **load-bearing for every
grounding, claim, and staleness pin**.

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

## How a printed label gets its depth

CFR numbers six paragraph levels: `(a)`, `(1)`, `(i)`, `(A)`, then an italic
`(1)` and an italic `(i)`. The stored section body keeps the labels but not the
italics, so a `(3)` that follows `(B)` could be (B)'s child or the next sibling
of an enclosing `(2)`, and an `(i)` that follows `(h)(2)` could be (2)'s first
child or paragraph (i). `_build_tree` decides by **sequence continuity**:

- A line-leading label (or one run in after a dash) goes where it is the next
  label of an open sibling sequence, or the first label of a new one. `(3)`
  after `(f)(2)(iii)(B)` continues `(1), (2)`; a list under (B) would start at
  `(1)`.
- When that holds at more than one depth, the placement the following labels
  confirm soonest wins: after `(i)`, a `(1)` or a `(j)` means paragraph (i), an
  `(ii)` or an `(A)` means a roman list. If several placements are confirmed
  equally soon, the deepest wins; if none is, one that continues a sequence
  beats one that would start a list of a single item.
- A label run in after a heading (`(d) Heading. (1)`, `(d) How? (1)`) or
  chained onto another label (`(d)(1)`) is taken only as the open paragraph's
  first child, and only if it is a first label (`1`, `i`, `A`). Anything else
  there is a cross-reference or a parenthetical.
- A range head, `(d)-(h) [Reserved]`, stands for every label it spans, so the
  `(i)` after it is the next paragraph.
- A run of labels followed by a citation phrase (`of this section`, `of this
  subchapter`, `of paragraph`, `of §`, `through`, `and (`, `, (`, `)`) cites
  other paragraphs and is not a head, even at a line start (a wrapped Federal
  Register line: `paragraph\n(d)(1)(i) of this section`) or after a colon.
  Lower-case text alone is not a citation: `(B) of those required to
  participate` is a paragraph.
- The section's first label sets the top-level form, read as the form in which
  it opens a list: a section that is one `(i), (ii), (iii)` list is roman.
- A label that skips ahead (`(a)` then `(d)`) is accepted where it does not
  restart a list. A label that continues no open sequence, such as a `(B)` with
  no `(i)` open or a mislabelled `(xxiv)` after `(xxviii)`, is left as text of
  the paragraph it sits in. It does not become a top-level node, which would
  cut every open paragraph short.

Invariants, for any body (`tests/test_provision_anchor_outline.py`):

1. **Tiling.** In document order, each leaf's text and each parent's lead-in
   (its text before its first child) follow one another with only whitespace
   between and no overlap; together they are the body from its first label on.
2. **Containment.** A child's span lies inside its parent's, and a span runs
   exactly to the next paragraph that is not inside it.
3. **Order.** Below the top level, sibling labels strictly increase. For an
   outline printed the way eCFR prints one, every sibling sequence is
   consecutive from its first label and the tree parses back to itself.
4. **Unique paths, or no anchors.** A body whose top-level list restarts
   (question-and-answer sections) raises rather than emit two rows for one
   path.
5. **Determinism.** The same body gives the same anchors.

These hold for a mis-nested tree too, so they are not what catches one. Two
checks do: the round-trip property, and a differential test against the
paragraph ids eCFR itself publishes (`<div id="p-435.603(f)(3)(iv)(A)">` in
`https://www.ecfr.gov/api/renderer/v1/content/enhanced/<date>/title-<n>?part=<p>&section=<s>`).
`tests/fixtures/provision_anchors/` holds those ids for nine section bodies and
for 7 CFR 273.9; the parser's paths must equal them.

What the text alone cannot decide:

- A second-level `(3)` that follows a fifth-level list which itself reached
  `(2)` reads equally well as that list's `(3)`. The parser keeps it in the
  deeper list. Only the source's italics settle this; carrying them into the
  section row is the fix.
- Items of a run-in enumeration after the first (`: (1) …; (2) …; and (3) …`)
  are not anchored; `(1)` spans the rest of its paragraph.
- Numbered lists under unlabelled definition terms, and older Treasury
  regulations that use a lower-case letter at the fourth level, are outside the
  ladder.

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
- Bump `EXTRACTOR_VERSION` whenever the algorithm could move offsets or
  paths; the `(parent provision, extractor_version)` pair is the rebuild cache
  key. `provision-anchors/2.0.0` (2026-10-10) changed which path a paragraph
  gets wherever 1.0.0 had filed it under the wrong parent. The 1.0.0 paths it
  retires (`us/regulation/7/273/9/c/1/vii/C/2` for 7 CFR 273.9(c)(2)) never
  named a real paragraph; rows generated by 1.0.0 must be regenerated, not
  migrated.
- CI regenerates the 7 CFR 273.9 and us-ma 106 CMR 365.180 artifacts and
  checks they equal the committed JSONL
  (`test_committed_*_anchors_match_generator`). Every committed artifact must
  also sit at the path of the provisions file it mirrors, verify against it,
  and carry its parent's jurisdiction, document class and version
  (`test_committed_anchor_artifact_tracks_its_provisions`).

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
  --provisions data/corpus/provisions/us/regulation/2026-05-10-snap-7-cfr-273-r2026-07-15-self-contained.jsonl \
  --target us/regulation/7/273/9 \
  --output data/corpus/anchors/us/regulation/2026-05-10-snap-7-cfr-273-r2026-07-15-self-contained.jsonl

# Resolve a citation path to (provision_id, span) over an anchors artifact.
axiom-corpus-ingest resolve-anchor \
  --anchors data/corpus/anchors/us/regulation/2026-05-10-snap-7-cfr-273-r2026-07-15-self-contained.jsonl \
  us/regulation/7/273/9/d/6/iii

# Optional: upsert an anchors artifact into corpus.provision_anchors.
axiom-corpus-ingest load-anchors-supabase \
  --anchors data/corpus/anchors/us/regulation/2026-05-10-snap-7-cfr-273-r2026-07-15-self-contained.jsonl \
  --provisions data/corpus/provisions/us/regulation/2026-05-10-snap-7-cfr-273-r2026-07-15-self-contained.jsonl
```

Before loading, note that `load-anchors-supabase` writes each anchor's
`parent_provision_id` as generated, which is the parent row's `id` in the
provisions JSONL. `load-supabase` replaces a path-only id
(`uuid5("axiom:" + citation_path)`) with the version-scoped
`deterministic_provision_id(citation_path, version)` and keeps any other id
(`provision_to_supabase_row` in `src/axiom_corpus/corpus/supabase.py`). Every
committed anchors artifact has path-only parent ids, so loading one today
points each anchor at whichever staged row holds that id rather than the row
its `version` names, or fails the foreign key if no row does.

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
