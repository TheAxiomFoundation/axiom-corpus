# ARM 37.78.420 without page chrome

`us-mt/regulation/2026-07-13-recovery` carries ARM 37.78.420 (TANF: assistance
standards; tables; methods of computing amount of monthly benefit payment) as
the whole rules.mt.gov page, and no other scope carries the rule (#757,
`2026-09-27-recovery-sibling-scopes-audit.md`, follow-up 2). This run builds its
successor, `us-mt/regulation/2026-07-13-recovery-r2026-09-27-chrome-free`, from
the same retained bytes. It keeps the one citation path; its row is the rule.

Nothing is published, loaded or activated, and no tracked selector is added or
edited. Which lines take the swap, and when, is queued for Max.

## What changes

| | `2026-07-13-recovery` | `…-r2026-09-27-chrome-free` |
| --- | --- | --- |
| Rows | 1, at `us-mt/regulation/title-37/chapter-37-78/subchapter-37-78-4/rule-37-78-420` | 1, same path |
| Body | 6,638 characters on one line. It starts with the page title, "Montana SOS Skip to main content Back View in PDF NEW" and the rule heading twice. The rule text follows, with history, MAR notices, references, "Referenced by" and the version list after it. | 4,768 characters: the rule text, one paragraph or table row per line (105 lines) |
| Tables | flattened; the post-employment cell reads `$ 37 5` | `Number of Persons in Household \| Gross Monthly Income (GMI)`, `1 \| $ 557`, …, `1st Month \| $ 375` |
| Heading, labels | none; `citation_label` `rule-37-78-420` | heading `TANF: ASSISTANCE STANDARDS; TABLES; …`, `citation_label` and `legal_identifier` `ARM 37.78.420` |
| Kind, level | `section`, 2 | `rule`, 4 (the Montana adapter's) |
| Parent | none | none (see below) |
| Metadata | `fetched_at`, `recovery_parser` | history (`history` and `source_history`), authorizing and implementing statutes, version 33678 and its uuid, effective start 2011-01-28, contact, `references_to`, MAR notices, referenced-by, the version list, and lineage (`successor_of_version`, `successor_of_source_path`, `verification_source_paths`) |
| `source_as_of`, `expression_date` | 2026-07-13 | 2026-07-13 |
| `id` | legacy path-only uuid | `deterministic_provision_id(path, version)`, as the loader computes anyway |

**Why the row has no parent.** Release validation checks parents within the scope
(`release_quality.py:767-777`) and citation paths across the whole release
(`:235-246`). The 42-15 income-tax scope, which the wave4 lines also select,
already emits the `us-mt/regulation` root. So a successor that emitted the
adapter's root would collide there. One that emitted `title-37` under that root
would lack its parent. The old row had no parent either. Navigation links a
parentless row to its nearest existing ancestor path (`navigation.py:14-19`).

## Source

**Retained page.** `official-documents/us-mt-arm-37-78` and its provenance
record are copied byte for byte from the recovery scope. The page is 170,570
bytes, sha256 `9d51d895…8406`, fetched by browser on 2026-07-14T21:17Z. The page
renders the rule's PDF with react-pdf. Its text layer
(`div.react-pdf__Page__textContent`, five pages) holds the whole rule document,
and its accordions and version list state the version facts. The Montana adapter
cannot read it: `_html_body_text` wants the API's accessible-HTML document,
which the page does not contain.

**Verification fetch (2026-09-27).** Using the API the adapter uses, `fetch`
downloaded three files: the policy JSON for policy
`81418fed-12b0-4ed9-a953-50b600e353d1`, and the PDF and accessible HTML of rule
version 33678. That is the version the retained page shows as active, with
uuid `d13f3962-…`, which the page's own version list links to. Each rendition's
sha256 is the `contentHashSha256` the policy JSON declares for it (`d3d670b4…`
for the PDF, `d94053c9…` for the HTML). The files sit under
`montana-rules/{policies,pdf,html}/`, each with a provenance record under
`provenance/` (`fetch_method` `http-get`, `declared_sha256`, `final_url`, and a
`purpose` field). They are checks only: every field of the row comes from the
retained page.

```bash
uv run --extra dev python scripts/repro/us_mt_arm_37_78_420_successor.py fetch --base data/corpus   # once, network
uv run --extra dev python scripts/repro/us_mt_arm_37_78_420_successor.py build --base data/corpus   # offline
```

## How the rule is read

`axiom_corpus.corpus.montana_rule_page` works in three steps; its docstring has
the details.

1. Spans with the same `top` on a page form a line.
2. The lines are split into four parts:
   - **Heading:** the lines before the first paragraph marker.
   - **Trailer:** everything from "Authorizing statute(s):" on. It is returned as fields.
   - **Paragraphs:** a line opening with `(1)`, `(a)`, … starts one; a one-span line at its text indent continues it.
   - **Tables:** everything else.
3. In a table:
   - A line opening with a row label (`1`, `20`, `1st`) starts a row, and later lines continue that row cell by cell.
   - Lines above the first row split into title and column-header rows. A gap wider than the text's line height starts a new row.

Wrapped lines join with a space, with two exceptions:
- A hyphen attached to a letter or digit joins the next line directly (`Post-` + `Employment`).
- Inside a table cell, a break inside a numeral joins directly (`$ 37` + `5`).

Anything the reader cannot place raises `MontanaRulePageError`: a heading
without an ARM number, a table without labelled rows, overlapping columns, or a
span without a position.

The reader keeps the official text as printed, including its errors. For
example, (1)(d) reads "based on the size of the or TANF cash assistance
Post-Employment Program benefits assistance unit" in the text layer, the PDF and
the accessible HTML alike.

## Checks against the version's own renditions

The build fails unless all of these hold (`check_against_verification_sources`):

- The policy JSON names version 33678 by the uuid the page links to, with the
  page's number and start date and the text layer's history note.
- The version's PDF and the text layer contain the same multiset of non-space
  characters (4,330).
- The version's accessible HTML, rendered one line per paragraph and one
  `a | b` line per table row, equals the heading, body and trailer rebuilt from
  the text layer, line for line (109 lines). This settles the wrapped cell: the
  HTML's cell reads `$ 375`.

`references_to` equals what the adapter's `_references_to` gives for the same
accessible HTML: ARM 37.78.103 and 37.78.406, then MCA 53-4-212, 53-4-211,
53-4-241 and 53-4-601. The history note is identical in the text layer, the
page's Rule History panel and the policy JSON.

## Rule version 33678 ended on 2026-09-25

The fetched policy JSON has a new active version, **AMD 2026-529, effective
2026-09-26**. Version 33678 now ends on 2026-09-25, and its history adds "AMD,
2026 MAR, Notice No. 2026-529, Eff. 9/26/26." On 2026-07-14 the retained page
listed the notice under "Referenced by" as "2026-529.1 TANF Benefit and Payment
Standards".

Its accessible HTML (sha256 `0726c6fd…`, the hash the policy JSON declares; read
2026-09-27T13:47Z and not committed) raises every table:

- The 3-person payment standard goes from $504 to $725.
- GMI for 1 person goes from $557 to $859, NMI from $312 to $464, and the
  benefit standard from $245 to $365.
- The PAYMENT STANDARDS table becomes CASH ASSISTANCE PAYMENT STANDARDS without
  the "33% of the FY 2007 Federal Poverty Level" note.
- The post-employment table ($375, $275, $175) is replaced. The new table pays
  $100 a month in months 1-6 and $50 a month in months 7-12, with a $300 Work
  Pays incentive in months 1, 7 and 12.
- It drops 53-4-601 from the implementing statutes.

This successor carries version 33678, the text in force on its
`expression_date`, 2026-07-13, and at every key line's cut (the latest,
snap-fy2027-cola, is 2026-09-24). The rulespec-us module encodes the same
version (`effective_from: '2011-01-28'`). A cut that should reflect Montana TANF
from 2026-09-26 needs a new ingest of AMD 2026-529 and a new version of the
module; both are split out below.

## Release lines

Each key line selects the recovery scope. The swap replaces it with the
successor and nothing else, so each line keeps its scope count. The citation
path set is unchanged (`test_the_swap_keeps_the_release_citation_set`), so
release-wide citation uniqueness cannot change either.

| Line | `us-mt/regulation` as selected | After the swap | `validate_release` on the swapped pair, profile and strict warnings |
| --- | --- | --- | --- |
| `us-rulespec-2026-08-08-obbb-alien-snap` (rulespec-us pin) | `2026-07-13-recovery` | `2026-07-13-recovery-r2026-09-27-chrome-free` | ok, 0 issues |
| `us-rulespec-2026-09-24-snap-fy2027-cola` | `2026-07-13-recovery` | `…-r2026-09-27-chrome-free` | ok, 0 issues |
| `us-rulespec-2026-08-23-canada-338-suspension-union` | `2026-07-13-recovery` | `…-r2026-09-27-chrome-free` | ok, 0 issues |
| `us-rulespec-2026-09-14-wave4-union` | `2026-07-13-recovery`, `2026-09-14-income-tax-regulations-title-42-section-42-15` | `…-r2026-09-27-chrome-free`, `2026-09-14-income-tax-regulations-title-42-section-42-15` | ok, 0 issues |
| `us-rulespec-2026-09-14-wave4-r2-union` | same as wave4 | same as wave4 | ok, 0 issues |

Never select the original with its successor. Validation rejects the pair with
`duplicate_release_citation`
(`test_selecting_the_original_with_its_successor_is_rejected`). axiom-encode's
resolver rejects it with `AmbiguousCorpusSourceError`
(`corpus_resolver.py:863-871`).

`corpus.activate_corpus_release` upserts `corpus.active_scope_pointer` for each
`(jurisdiction, document_class)` pair a release carries
(`supabase/migrations/20260719043000_profiled_release_activation.sql:254-288`).
The swap therefore takes effect when a cut that carries the pair is activated.

## Downstream

The resolver check used axiom-encode origin/main `7cd931de` (its
`corpus_resolver.py` is unchanged since the rulespec-us toolchain pin
`06b01708`) and rulespec-us origin/main `54d90a72`. It ran the #757 resolver
script with its swap for this scope set to "add the successor". One rulespec-us
module cites the path: `us-mt/regulations/title-37/chapter-37-78/subchapter-37-78-4/rule-37-78-420.yaml`.
Results were the same in all five lines:

| | Resolves to | Slice | Body chars | Body sha256 |
| --- | --- | --- | ---: | --- |
| As selected | `2026-07-13-recovery` | no | 6,638 | `83beb578…` |
| After the swap | `2026-07-13-recovery-r2026-09-27-chrome-free` | no | 4,768 | `3c28fc09…` |

On the module, axiom-encode's proof validation passes 8 of 8 atoms against
either body. Its numeric grounding finds one ungrounded literal in the old body,
375, which the body splits as `$ 37 5`, and none in the successor.

The module sits under an active validation waiver (`known-validation-gaps.yaml`,
fingerprint `sha256:7507f0c5…`, rulespec-us#782). The fingerprint hashes the
module's validation issues (`validation_waivers.py:582-615`). So once a re-pin
selects the successor, the waiver audit will report it stale or drifted. The
re-pin must update or remove the waiver.

## Invariants

- **Faithfulness (differential):** the text-layer reading equals the version's
  accessible HTML line for line, and the text layer carries exactly the PDF's
  characters. Both are checked at build and in tests.
- **Conservation:** every non-space character of the text layer appears in the
  heading, body or trailer, and nothing else does, apart from the `|` cell
  separators (`test_every_text_layer_character_is_kept`, and the same on 57
  synthetic pages).
- **Round trip (property):** 400 seeded synthetic rules, laid out as the text
  layer lays them out, read back to exactly their source lines. The layouts
  include page breaks, hyphen and numeral wraps, wrapped headers, and ordinal
  labels. Breaking any one rule makes seeds fail: without the numeral join 293
  fail, without the hyphen join 331, and with a table-local line pitch 224.
  The tests use `random.Random` with fixed seeds; Hypothesis is not a
  dependency here.
- **Reproducibility:** `build` rewrites every committed file of the scope byte
  for byte, from `data/corpus` alone.
- **Lineage:** the retained page and its provenance are byte-identical to the
  recovery scope's, and the inventory hash is unchanged.

## Follow-ups

1. **AMD 2026-529.** Ingest the current version (Montana adapter, fresh fetch,
   new provenance). Its scope must not select this path alongside the
   successor, so it needs either its own citation-path decision or a later swap.
2. **rulespec-us.** On the re-pin that selects this successor, update or remove
   the waiver for the module. Then encode AMD 2026-529 as a new version of the
   module through the encoder.
3. **Other retained rules.mt.gov pages.** `montana_rule_page` reads any
   rules.mt.gov rule page with a react-pdf text layer. No other scope holds one.
   The only other inventory that points at rules.mt.gov is the adapter's 42-15
   scope, which reads the API.

## Checks

Run on `origin/main` f1916d73b with this branch's files, in a sparse checkout
holding `data/corpus/sources/us-mt/`:

- `pytest tests/test_montana_rule_page.py tests/test_us_mt_arm_37_78_420_successor.py`: 792 passed.
- `pytest tests/test_corpus_montana_admin_rules.py tests/test_idaho_statute_successor.py
  tests/test_ingest_manifest_provenance.py`: passed. `tests/test_recover_ingest.py`
  has 21 failures, all `FileNotFoundError` on sources that the sparse checkout
  leaves out.
- `axiom-corpus-ingest coverage … --document-class regulation --write`:
  complete, 1 of 1, file unchanged.
- `validate_release` on each swapped pair: see the table above.
- `ruff check`, `ruff format --check`, and `mypy src/axiom_corpus/corpus` and the
  script: clean.
- `towncrier check --compare-with origin/main`: finds
  `us-mt-arm-37-78-420-successor.fixed.md`.

## Signing

The artifacts are committed first (`git add -f`, since `data/` is ignored).
Then, from that clean commit:

```bash
AXIOM_CORPUS_INGEST_PRIVATE_KEY="$(agent-secret get agent/axiom-corpus-ingest-private-key)" \
uv run --extra dev axiom-corpus-ingest sign-ingest-manifest \
  --repo . --base data/corpus \
  --jurisdiction us-mt --document-class regulation \
  --version 2026-07-13-recovery-r2026-09-27-chrome-free \
  --command 'uv run --extra dev python scripts/repro/us_mt_arm_37_78_420_successor.py build --base data/corpus (verification sources: … fetch --base data/corpus, 2026-09-27; run note: docs/ingest-runs/2026-09-27-us-mt-arm-37-78-420-successor.md)'
```

The manifest is committed on its own. `guard-ingested --base-ref origin/main`
then verifies it with the repository's public key.
