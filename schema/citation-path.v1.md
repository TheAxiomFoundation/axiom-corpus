# Citation-path grammar, v1

Status: published, versioned (`v1`). Additive and descriptive — this document
does not rename any existing path.
Machine-readable form: [`schema/citation-path.v1.json`](./citation-path.v1.json).
Enforcement: [`scripts/validate_citation_paths.py`](../scripts/validate_citation_paths.py),
tests in [`tests/test_citation_path_grammar.py`](../tests/test_citation_path_grammar.py).

Phase-A item **A6** of `axiom-rebuild-plan-2026-07-02.md`: *"Citation-path
grammar + segmentation rules published as a versioned schema … prerequisite for
any re-extraction ever being diffable; provision IDs are uuid5(citation_path),
so path identity IS identity."*

This grammar was **derived empirically** from every record in
`data/corpus/provisions/**/*.jsonl` in the RuleSpec UK promotion tree based on
`origin/main @ 06f4d429fd5d3bbc1426217c4b9396abbcccfed3` (64,457 records,
63,860 unique paths). The JSON file's regexes are normative; this document
explains them and specifies the identity contract and the path-mapping event
vocabulary that future release diffs must emit.

---

## 1. What a citation path is

Every corpus provision carries a `citation_path`: a slash-delimited,
hierarchical, human-legible identifier that locates the provision within a
source document. It is also the provision's **stable identity** — see §5.

```
us-ny/statute/NYC/11-1701
└──┬─┘ └──┬──┘ └─────┬────┘
 seg 0   seg 1    seg 2+  (source hierarchy → leaf)
jurisdiction  document_class
```

Rules that hold for every path:

- No leading slash, no trailing slash, no empty segments, no `//`.
- Segment 0 is the **jurisdiction**; it equals the record's `jurisdiction`
  field.
- Segment 1 is the **document_class**; it equals the record's `document_class`
  field and is one of a closed set of seven values.
- Segments 2+ are source-specific hierarchy tokens down to the leaf provision.
- A bare `<jurisdiction>/<document_class>` (no hierarchy segment) is valid
  **only** for collection-root records (`kind: collection`, `level: 0`).

Normative pattern (see JSON `$defs.citation_path.pattern`):

```
^[a-z]{2,3}(?:-[a-z]{2,32})*/(statute|regulation|manual|guidance|policy|form|rulemaking)(/[A-Za-z0-9][A-Za-z0-9 .\-–]*)*$
```

## 2. Segment 0 — jurisdiction

Pattern: `^[a-z]{2,3}(?:-[a-z]{2,32})*$`.

- **National**: a bare code — `us`, `uk`, `be`. Federal / national source text
  lives here (Title 26 IRC under `us`, UK primary legislation under `uk`,
  Belgian federal `loi` under `be`).
- **Subnational or local authority**: a national root followed by one or more
  lowercase tokens. US states use postal codes (`us-ca`, `us-ny`, …). Belgian
  regions use `be-vlg` (Flanders), `be-wal` (Wallonia), `be-bru` (Brussels),
  `be-dg` (German-speaking Community). UK local schemes use the issuing
  authority, for example `uk-kingston-upon-thames`.

Observed slugs are enumerated in the JSON `observed` list. The pattern is
intentionally broader than that set so a new state, region, or local authority
validates without a schema bump; new slugs **should** still be appended to
`observed` so the enumeration stays a faithful inventory.

## 3. Segment 1 — document_class

A closed enumeration of seven values (JSON `$defs.document_class.enum`):

| class | meaning | volume note |
|---|---|---|
| `statute` | Codified primary legislation (US Code, UK ukpga, Belgian loi, state codes) | |
| `regulation` | Administrative / secondary legislation (CFR, state admin codes, UK uksi, Belgian arrete) | |
| `manual` | Agency operational manuals / eligibility source books | largest class; heavily paginated |
| `guidance` | Sub-regulatory guidance (IRS rev. procs, SSA determinations, ACLs/ACINs) | |
| `policy` | State plans and policy documents (TANF/SNAP state plans) | |
| `form` | Official forms and their published parameter tables | |
| `rulemaking` | In-progress rulemaking dockets (e.g. NJAC proposed rules) | |

Adding a new document_class is a **grammar change** (a `v1 → v1.x` schema edit),
not a data-only change, because the enum is normative.

## 4. Segments 2+ — source hierarchy and the family conventions

Each hierarchy segment matches `^[A-Za-z0-9][A-Za-z0-9 .\-–]*$`: it starts with
an alphanumeric and may contain letters, digits, spaces, dots, hyphens, and
en-dashes (U+2013). Uppercase and spaces are permitted because they appear in
real published citation labels. The recurring shapes below are **documentary**
conventions per (jurisdiction, document_class) cluster — the validator checks
the charset, not family membership, so new families are expected as coverage
grows.

| family | shape | example |
|---|---|---|
| US federal statute | `us/statute/<title>/<section>[/<sub>…]` | `us/statute/26/3121/a/1` |
| US federal regulation | `us/regulation/<title>/<part>[/<section>\|/subpart-<X>…]` | `us/regulation/7/273/9` |
| UK statute | `uk/statute/ukpga/<year>/<chapter>/<section>` | `uk/statute/ukpga/1992/12/1K` |
| UK regulation | `uk/regulation/uksi/<year>/<number>/<article>` | `uk/regulation/uksi/2013/376/24A` |
| Belgium statute | `be[-region]/statute/<instrument>/<yyyy>/<mm>/<dd>/<eli-id>/article/<n>` | `be/statute/loi/1989/01/16/1989021010/article/N` |
| US state manual (paginated) | `us-XX/manual/<agency>/…/page-<n>` | `us-or/manual/odhs/…/page-42` |
| UK local-authority manual (paginated) | `uk-<local-authority>/manual/<document>/page-<n>` | `uk-kingston-upon-thames/manual/council-tax-reduction-scheme-2026-2027/page-42` |
| US state regulation | `us-XX/regulation/<code>/<part>/<section>[/<sub>\|/block-<n>]` | `us-ma/regulation/106-cmr/365/180/block-1` |

### 4.1 Corpus namespace vs rulespec module namespace (do not confuse)

The corpus citation_path for a federal regulation is
`us/regulation/7/273/9` (singular `regulation`, numeric title). The **rulespec-us
module path** for the same law is `us/regulations/7-cfr/273/9.yaml` (plural
`regulations`, hyphenated `7-cfr`). These are different namespaces. The corpus
form is the canonical `citation_path`; a rulespec module ties back to it through
its `module.source_verification.corpus_citation_path` field. Program specs in
`axiom-programs` scope on the **module** namespace. This distinction is at the
heart of `axiom-programs#14` (see `docs/granularity-policy-proposal.md`).

### 4.2 Irregular families (valid, tracked, ratcheted)

These segment idioms deviate from a clean legal tokenization but are **valid and
expected**. Each has a live count and a ratcheted ceiling in the JSON
`known_irregulars_ratchet`; the validator fails if a count *grows* past baseline
(a regression), not if it shrinks.

| family | fragment | why it exists | r0 count |
|---|---|---|---|
| `block-N` | `/block-<n>` | synthetic leaf for an un-subdivided chunk (whole section, table, paragraph run) the extractor could not sub-identify | 18,509 |
| `page-N` | `/page-<n>` | ordinal page of a paginated source (PDF/long HTML); structural, not legal | 19,571 |
| uppercase | — | US subsection letters (`subpart-A`), UK suffixes (`228ZA`), Belgian `N` annexes, verbatim state labels (`He-W 766.01`) | 5,205 |
| spaces | — | verbatim published labels; AK (`7 AAC 45.010`) and NH (`He-W 766.01`) | 196 |
| en-dash | `–` | ranged labels from source text | 21 |
| truncated | trailing `-`/space | **data smell**: heading truncated when the slug was built; all in `us-ut/manual/dws/eligibility-manual`. The trailing punctuation is meaningless; the durable fix is upstream slug generation | 53 |
| collection roots | `<jur>/<class>` | container records (`kind: collection`), not leaf provisions; no parent, not groundable | 9 |

## 5. Identity: the path IS the provision

Provision UUIDs are derived deterministically from the citation path. Two forms
exist in the code (both `uuid5` over `NAMESPACE_URL`):

- **Path-only** (historical, `src/axiom_corpus/ingest/supabase.py`
  `_deterministic_id`, and `src/axiom_corpus/corpus/supabase.py`
  `deterministic_provision_id` when no version is passed):

  ```python
  uuid5(NAMESPACE_URL, f"axiom:{citation_path}")
  ```

- **Versioned** (`deterministic_provision_id` with a release version, so the
  same citation can coexist across staged/published versions):

  ```python
  uuid5(NAMESPACE_URL, json.dumps(["axiom", version, citation_path], separators=(",", ":")))
  ```

Across the r0 corpus, 51,404 of 51,428 stored IDs (99.95%) reproduce from one of
these two forms against the current path.

**The consequence is the whole point of A6:** because the UUID is a pure
function of the path, **changing a path changes the provision's identity**. A
re-segmentation is not an edit — it deletes one provision (old UUID) and creates
another (new UUID). Everything keyed on provision identity dangles:
`rulespec` module `corpus_citation_path` fields, claim subjects, the
`provisions_to_rules` reverse index (`rulespec-us#523`), and any anchor.

### 5.1 Identity drift observed at r0

The validator tracks paths whose stored `id` reproduces from **neither** form —
i.e. the path was edited *after* the UUID was minted, so the stored identity no
longer derives from the current path. At r0 there are **21** such paths
(enumerated in the JSON `identity_drift_ratchet.baseline_paths`), in three
clusters:

- `us/regulation/42/435/550`…`563` (14) — CMS Medicaid community-engagement
  regulation (42 CFR 435), re-segmented after ingest.
- `us-ny/policy/otda/tanf-state-plan-2024-2026/…` (4) — NY TANF state plan.
- `us-ma/…` (3) — MA DTA SNAP-COLA guidance and `106-cmr/365/180/A`.

These are **tracked, not tolerated**. The validator fails if the set grows. The
correct remediation is to re-ingest the affected provisions (so the stored UUID
matches the path again) *and* emit the path-mapping events in §6 so downstream
consumers can follow. Note that the MA cluster (`106-cmr/365/180/A` and the DTA
SUA path) is the **corpus side of the same drift** that surfaces as dangling
scope entries in `axiom-programs#14`.

## 6. Path-mapping event vocabulary (spec only — no implementation here)

Because identity is the path, any future release that changes paths **must**
emit a machine-readable path-mapping event stream alongside the provision diff,
so that consumers can migrate deterministically instead of silently dangling.
This section specifies the vocabulary; implementation lands in a later release
(it is out of scope for this additive PR).

Each event is a JSON object with a `type`, the release `version` it belongs to,
and the affected path(s). Old and new provision UUIDs are included because they
are what consumers actually key on.

### 6.1 Event types

| `type` | meaning | cardinality |
|---|---|---|
| `rename` | one provision's path changed; content identity preserved | 1 old → 1 new |
| `split` | one provision was segmented into several finer provisions | 1 old → N new |
| `merge` | several provisions were collapsed into one coarser provision | N old → 1 new |
| `move` | subtree re-parented (prefix change) without content change | 1 old-prefix → 1 new-prefix (fans out to all descendants) |
| `retire` | provision removed with no successor | 1 old → 0 |
| `introduce` | genuinely new provision with no predecessor | 0 → 1 new |

`rename` and `move` are content-preserving (a consumer can re-point
mechanically). `split`/`merge` are **not** content-preserving: a consumer
grounded on the old provision must be re-reviewed, because the text it cited now
lives in a different granularity. `retire` must dangle loudly.

### 6.2 Event shape

```json
{
  "type": "split",
  "version": "2026-07-15-cms-2454-ifc-42-cfr-435-community-engagement",
  "from": {
    "citation_path": "us/regulation/42/435/550",
    "provision_id": "10abd1ff-9c8b-55e4-9dfd-ec7350570ca0"
  },
  "to": [
    {"citation_path": "us/regulation/42/435/550/a", "provision_id": "…"},
    {"citation_path": "us/regulation/42/435/550/b", "provision_id": "…"}
  ],
  "reason": "re-segment section 550 to subsection granularity per axiom-programs#14",
  "content_preserving": false
}
```

`provision_id` values are computed with the identity formula in §5 (versioned
form when the release carries a version). `rename`/`move` use a single `to`
object; `merge` uses a list under `from` and a single `to`; `retire` omits `to`;
`introduce` omits `from`.

### 6.3 Where events live and who consumes them

- Emitted per release into a `path-mapping/<version>.jsonl` stream (location to
  be finalized when implemented).
- Consumed by: rulespec `corpus_citation_path` migration, claims re-keying (A4),
  reverse-index regeneration (`rulespec-us#523`), and any anchored reference
  (see the granularity proposal).
- The stream is **append-only** and part of the signed corpus release manifest
  (A2), so a re-extraction is diffable and a consumer can replay the mapping to
  migrate without guessing.

## 7. Versioning of this grammar

- **`v1`** = this document + `citation-path.v1.json`.
- A change to the segment charset, the jurisdiction pattern, the document_class
  enum, or the identity formula is a **new schema version** (`v1.1`, `v2`) with
  a changelog fragment. Adding to the `observed` jurisdiction list, raising a
  ratchet baseline via the reviewed `--update-baselines` path, or documenting a
  new family are **`v1` amendments** (patch-level) and stay in these files.
- The validator always reads the schema file, so bumping the schema and its
  baselines is the single point of change.
