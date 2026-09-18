# Wave-4 citation-path slugs: NE, CT, CO, DE, AL re-extracted as `-r2`

Date: 2026-09-14
Branch `fix/wave4-citation-path-slugs` cut from `origin/main` in the sparse worktree
`~/axiom-corpus-worktrees/slug-fix` (`data/corpus/` excluded, never symlinked); every extraction
wrote to the main checkout's corpus root (`--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`).

## Problem

The citation-path grammar gate (`scripts/validate_citation_paths.py`, `schema/citation-path.v1.json`)
rejected 398 paths in five wave-4 scopes that were held out of the 2026-09-14 release PR (#710).
A hierarchy segment may contain only `[A-Za-z0-9]`, space, `.`, `-` and the en-dash; the adapters
had passed the publisher section identifiers through verbatim:

| scope | failing paths | cause |
|---|---:|---|
| `us-ne/statute/2026-09-14-income-tax-chapter-us-ne-title-77` | 218 | Nebraska numbers the later sections of an article with a comma (`77-3,100`) |
| `us-ct/regulation/2026-09-14-income-tax-regulations` | 146 | RCSA section ids carry the statute subsection in parentheses (`12-740(a)-1`) |
| `us-co/regulation/2026-09-14-income-tax-regulations` | 31 | 1 CCR 201-2 rule numbers carry parenthesised subsections (`39-22-103(1)`); 37 more used the en-dash rule counter (`39-22-303–1`), grammar-valid but ratcheted |
| `us-de/statute/2026-09-14-income-tax-chapter-us-de-title-30-chapter-11` | 2 | combined repealed headings `§§ 1159, 1160` (the publisher's own `id`) |
| `us-al/statute/2026-09-14-income-tax-chapter-us-al-title-40` | 1 | a second ALISON node for `40-21-123` ("Effective Upon Ratification...") was disambiguated as `40-21-123@code-28957` |

The released corpus (every other provisions file on disk) has no path containing `,`, `(`, `)` or
`@`; the precedents for the same shapes are the CT statute scope `us-ct/statute/12-700-a-10`
(CGS § 12-700(a)(10), parentheses to hyphens), the documents extractor's ranged labels
(`8.139.502.9-10`), and the NM/VT same-number variants `7-1-6.21--effective-2027-07-01` /
`32-5930ll--effective-2030-07-01` (`--` separator).

## Slug rules (code changes)

`src/axiom_corpus/corpus/citation_segment.py` (new) is the one funnel:

- `citation_segment(value, *, normalize_dashes=False)`: every run of characters outside the grammar
  alphabet, together with any hyphens, dashes or whitespace touching that run, folds into a single
  hyphen; such a run at the start or end of the segment is dropped. Characters the grammar accepts are
  left exactly as they are, so a segment that was valid before is returned unchanged (spaces,
  uppercase, dots, en-dashes and trailing hyphens are not rewritten) and no released path moves.
  With `normalize_dashes=True`, en-dashes and em-dashes become hyphens first.
- `variant_segment(segment, variant)` joins a same-number variant with `--` (NM/VT convention).
- The publisher identifier is kept verbatim in provision metadata: `metadata.publisher_section_id`
  is set on every row whose segment differs from the publisher's id (in addition to the adapter
  fields that already held it: NE `metadata.section`, DE `display_number`, AL `display_id` /
  `code_id` / `canonical_citation_path`, official documents `section_label`).

| publisher id | before | after |
|---|---|---|
| NE `77-3,100` | `us-ne/statute/77/77-3,100` | `us-ne/statute/77/77-3-100` |
| CT `12-740(a)-1` | `.../income-tax/12-740(a)-1` | `.../income-tax/12-740-a-1` |
| CT `12-701(a)(20)-1` | `.../income-tax/12-701(a)(20)-1` | `.../income-tax/12-701-a-20-1` |
| CO `39-22-103(1)` | `.../1-ccr-201-2/39-22-103(1)` | `.../1-ccr-201-2/39-22-103-1` |
| CO `39-22-104(1.7)` | `.../1-ccr-201-2/39-22-104(1.7)` | `.../1-ccr-201-2/39-22-104-1.7` |
| CO `39-22-303–1` | `.../1-ccr-201-2/39-22-303–1` (en-dash) | `.../1-ccr-201-2/39-22-303-1` |
| DE `1159, 1160` | `us-de/statute/30/1159, 1160` | `us-de/statute/30/1159-1160` |
| AL `40-21-123` (code 28957) | `us-al/statute/40-21-123@code-28957` | `us-al/statute/40-21-123--code-28957` |

Adapter wiring:

- `documents.py`: `_block_citation_path` runs every `citation_suffix` segment through
  `citation_segment` (after the existing `safe_segment`), and both the inventory items and the
  provision records carry `publisher_section_id` when the segment changed. New extraction option
  `normalize_citation_segment_dashes: true` (set in `manifests/us-co-income-tax-regulations.yaml`)
  folds the CO en-dash rule counter to a hyphen; the option is opt-in so the 1,652 released en-dash
  paths of other scopes are untouched on re-ingest.
- `states.py` (Nebraska): `_nebraska_section_citation_path` slugs the section number for section
  rows, inventory items and `references_to`; `metadata.publisher_section_id` added.
- `state_adapters/delaware.py`: the section segment is slugged and a same-number variant now joins
  with `--` instead of `@` (no released DE path had a variant); `publisher_section_id` field.
- `state_adapters/alabama.py`: section paths are slugged; the duplicate-number disambiguator is
  `--code-<code_id>` instead of `@code-<code_id>`; `publisher_section_id` on both the slugged and
  the variant rows.
- Tests: `tests/test_citation_segment.py` (new, rules, idempotence, grammar match), plus new cases
  in `test_corpus_documents.py` (CT-shaped HTML labels and the dash option),
  `test_corpus_delaware.py` (`§§ 1159, 1160`, `--` variants), `test_corpus_alabama.py` (repeated
  section number) and `test_corpus_states.py` (`77-27,187`).

## Re-extraction

The five scopes were re-run with the fixed adapters under new version strings so the held-out
artifacts were not overwritten. The state statute adapters append their own scope suffix to the
manifest version, so the `-r2` marker sits on the version prefix
(`2026-09-14-income-tax-chapter-r2` in `manifests/state-income-tax-chapters-2026-09-14.yaml` for the
AL, DE and NE sources; the other sources keep `2026-09-14-income-tax-chapter`). The NE/DE/AL runs
read the download caches of the first run (no publisher traffic); CT and CO were re-fetched from
eRegulations and the SOS `GenerateRulePdf` endpoint on 2026-09-14 (`--source-as-of 2026-09-14
--expression-date 2026-09-14`, as the first run). Row counts, section bodies, coverage and empty-body
counts are identical to the held-out scopes; only the listed segments changed.

| scope (new version) | rows | complete | renamed paths | `publisher_section_id` rows | empty section bodies | grammar |
|---|---:|---|---:|---:|---:|---|
| `us-ne/statute/2026-09-14-income-tax-chapter-r2-us-ne-title-77` | 2,742 | yes, 0 missing, 0 extra | 218 | 218 | 801 (publisher's repealed/transferred placeholders, as before) | 0 failures |
| `us-ct/regulation/2026-09-14-income-tax-regulations-r2` | 187 | yes | 146 | 146 | 0 | 0 failures |
| `us-co/regulation/2026-09-14-income-tax-regulations-r2` | 106 | yes | 68 (31 parenthesised + 37 en-dash) | 68 | 2 (as before) | 0 failures |
| `us-de/statute/2026-09-14-income-tax-chapter-r2-us-de-title-30-chapter-11` | 103 | yes | 2 | 2 | 5 (as before) | 0 failures |
| `us-al/statute/2026-09-14-income-tax-chapter-r2-us-al-title-40` | 2,265 | yes | 1 | 1 | 0 | 0 failures |

Verification:

- `python scripts/validate_citation_paths.py --provisions <tree holding only the five new files>`:
  5,403 records, 5,403 unique paths, 0 pattern failures, 0 jurisdiction/document_class mismatches,
  `RESULT: OK`; irregular families in the five files: en-dash 0 (the first run would have added 38
  against a baseline the rest of the tree already fills exactly), uppercase 271, no block/page/space/
  truncated segments.
- Every new row's body equals the body of the held-out row with the same publisher identifier
  (0 mismatches across the five scopes); no duplicate citation paths inside any scope.
- Collisions against every same-jurisdiction scope of
  `manifests/releases/us-rulespec-2026-09-14-wave4-union.json` (read from the release branch,
  read-only): NE 3, DE 6 and AL 3 paths collide with the `2026-07-13-recovery` statute scopes the
  new scopes supersede (the same three swaps the 2026-09-14 statute note lists; the recovery paths
  not in the new scopes are NE's ten `block-N` sub-rows of those three sections; DE and AL have none).
  CT and CO share no path with any selector scope. The held-out first-run scopes are not in the
  selector; they share the unchanged paths with the `-r2` scopes and must not be added alongside them.
- Cited-path check (rulespec-us commit c8951033, `~/rulespec-us/us-xx`): every path rulespec-us
  cites in the three superseded recovery scopes is in the new scope: NE 3 / 3 / 0 / none
  (`77/77-2715.03`, `77/77-2715.07`, `77/77-2716.01`), DE 6 / 6 / 0 / none (`30/1102`, `1108`,
  `1109`, `1110`, `1114`, `1117`), AL 3 / 3 / 0 / none (`40-18-5`, `40-18-15`, `40-18-19`). None
  of the cited paths was among the renamed segments.

## Manifests and queue

- `manifests/state-income-tax-chapters-2026-09-14.yaml`: AL, DE, NE sources at
  `version: "2026-09-14-income-tax-chapter-r2"`.
- `manifests/us-co-income-tax-regulations.yaml`: `normalize_citation_segment_dashes: true`.
- `manifests/tax-agent-queue.yaml`: the NE/DE/AL `income_tax_chapter_scope` rows (versions,
  coverage version, note) and the CT/CO `target_scope` versions point at the `-r2` scopes;
  `scripts/state_tax_ty2026_amounts.py` `STATUTE_ROWS` carries the same versions so a regeneration
  does not revert the queue.
- The 2026-09-14 statute and regulation run notes and their draft selector JSONs are left as the
  record of the first run; the Controller table below replaces their five entries.

## Checks

- `uv run ruff check .`: clean.
- `uv run --extra dev pytest -q tests/test_citation_segment.py tests/test_corpus_delaware.py
  tests/test_corpus_alabama.py tests/test_corpus_documents.py
  tests/test_corpus_documents_styled_labeled_docx.py tests/test_corpus_artifacts_coverage.py
  tests/test_citation_path_grammar.py`: 176 passed, 1 failed
  (`test_corpus_is_nonempty`, which reads `data/corpus` that the sparse worktree does not hold, as in
  the earlier notes); `tests/test_corpus_states.py`: 57 passed.
- GitNexus MCP tools were not available in this session; the blast radius was checked by hand:
  `_block_citation_path` (two callers in `documents.py`), the NE path builders (extractor,
  inventory and `references_to` only), `_section_from_tag` (DE) and the AL de-duplication loop.

## Controller

Artifacts are unsigned, on the controller's disk under `/Users/pavelmakarchuk/axiom-corpus/data/corpus`
(provisions, inventory, coverage, sources), not committed; no `.axiom/ingest-manifests` entry exists
yet for the `-r2` versions. Remaining steps are the controller's: `sign-ingest-manifest` per scope,
merge into the next selector (in place of the five held-out first-run scopes), re-validate, sign,
publish, activate.

| action | jurisdiction | document_class | version |
|---|---|---|---|
| remove | us-al | statute | 2026-07-13-recovery |
| add | us-al | statute | 2026-09-14-income-tax-chapter-r2-us-al-title-40 |
| add | us-co | regulation | 2026-09-14-income-tax-regulations-r2 |
| add | us-ct | regulation | 2026-09-14-income-tax-regulations-r2 |
| remove | us-de | statute | 2026-07-13-recovery |
| add | us-de | statute | 2026-09-14-income-tax-chapter-r2-us-de-title-30-chapter-11 |
| remove | us-ne | statute | 2026-07-13-recovery |
| add | us-ne | statute | 2026-09-14-income-tax-chapter-r2-us-ne-title-77 |

Do not add the five first-run versions (`...-income-tax-chapter-us-ne-title-77`,
`...-us-de-title-30-chapter-11`, `...-us-al-title-40`, `us-ct/regulation/2026-09-14-income-tax-regulations`,
`us-co/regulation/2026-09-14-income-tax-regulations`); they fail the grammar gate and share paths
with the `-r2` scopes.

## Rebuild

```bash
B=/Users/pavelmakarchuk/axiom-corpus/data/corpus
uv run axiom-corpus-ingest extract-state-statutes --base $B \
  --manifest manifests/state-income-tax-chapters-2026-09-14.yaml \
  --only-jurisdiction us-ne --only-jurisdiction us-de --only-jurisdiction us-al
for st in ct co; do
  uv run axiom-corpus-ingest extract-official-documents --base $B \
    --version 2026-09-14-income-tax-regulations-r2 --manifest manifests/us-$st-income-tax-regulations.yaml \
    --source-as-of 2026-09-14 --expression-date 2026-09-14
done
```
