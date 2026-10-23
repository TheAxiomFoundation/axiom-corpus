# 2026-10-20 — Utah eRules address repair (us-ut benefit and TANF regulation scopes)

The Utah Office of Administrative Rules relaunched eRules v1.0.0 on 2026-10-16
([announcement](https://rules.utah.gov/new-erules-launch-october-16/)). Every old public address on
`adminrules.utah.gov` now answers HTTP 404. The 2026-10-20 wave-8 state-tax run found this while taking
R865-9I and recorded it in `docs/ingest-runs/2026-10-20-w8-state-tax-regulations.md`, which names the
scopes outside that run as a separate work order. This note is that work order.

Nothing was lost. The retained sources of the affected scopes are untouched, the rule versions behind them
are unchanged, and every repaired scope rebuilds with byte-identical provision bodies. Only the recorded
addresses, the extraction content selector and the retained source bytes change.

## What broke

Read on 2026-10-20 with the plain corpus client (`OFFICIAL_DOCUMENT_USER_AGENT`, TLS verification on):

| Address | Status | Body |
| --- | --- | --- |
| `/public/rule/R986-200/Current%20Rules` | 404 | 64,076-byte application 404 page |
| `/public/rule/R414-306/Current%20Rules` | 404 | same |
| `/public/rule/R994-401/Current%20Rules` | 404 | same |
| `/api/public/getfile/uac-html/1a059e78-…html/R986-200.html` | 404 | same |
| `/api/public/getfile/uac-html/1f7c0fac-…html/R414-306.html` | 404 | same |
| `/api/public/getfile/uac-html/ffc52bcf-…html/R994-401.html` | 404 | same |
| `/api/public/getHTML/uac-html/1a059e78-…html` | 404 | same |
| `/api/public/searchRuleDataTotal/R414-306/Current%20Rules` | 404 | same |

Every one answers the same 64,076-byte page, so the 404 is the route, not the rule.

## The live API and routes

- `POST /api/search`, body `{"searchTerm": "<rule or title>", "ruleTypeId": 51}`. Returns agencies ->
  `titleResults` -> `ruleResults`, each entry a `{ruleId, ruleVersionId}` pair and nothing else. The
  `ruleTypeId` enum is `currentRules=51`, `deletedRules=52`, `emergencyRules=53`,
  `expiredEmergencyRules=54`, `proposedRules=55`, `repealedRules=56`, `supersededRules=57`.
- `POST /api/ruleVersion`, body `{"ruleTypeId": 51, "versionIds": [...]}`. Returns the per-rule records
  that name `ruleReference`, `ruleName`, `effectiveDateString` and `docxName`/`htmlName`/`pdfName`.
  **A rule reference is resolved in two calls, not one:** the search payload carries no reference number.
- Rule page `https://adminrules.utah.gov/Rule/{ruleId}/{ruleTypeId}/{ruleVersionId}/undefined`. The
  trailing `/undefined` segment is required; all three pages answer 404 without it (verified per page).
  The page server-renders the publisher's own converted rule HTML (Aspose `div.awdiv` / `span.awtext1`)
  into the DOM. No request options are needed: the plain client gets the full body.
- `GET /api/storage/<file>` answers HTTP 500 for the exact `htmlName` a rule-version record gives, and a
  JSON 404 for a URL-encoded `uac-html/<file>` key. No direct file route is used anywhere in this repair.

## Rules resolved

| Rule | ruleId | ruleVersionId | Repaired page | `htmlName` | `effectiveDateString` |
| --- | ---: | ---: | --- | --- | --- |
| R986-200 Family Employment Program | 2196 | 4835 | `/Rule/2196/51/4835/undefined` | `1a059e78-…` | 10/24/2022 |
| R414-306 Program Benefits and Date of Eligibility | 980 | 7248 | `/Rule/980/51/7248/undefined` | `1f7c0fac-…` | 06/19/2025 |
| R994-401 Payment of Benefits | 2241 | 4501 | `/Rule/2241/51/4501/undefined` | `ffc52bcf-…` | 04/21/2022 |

Each `ruleId` matches the `rule_id` the affected manifest already recorded, each `htmlName` UUID matches
the UUID in the dead `download_url` it replaces, and each `effectiveDateString` matches the recorded
`effective_date`. **The rule versions are the same ones the original runs took**, so no `expression_date`
and no `source_as_of` was changed: this repair moves addresses, it does not take a new expression.

## Files repaired

| File | Change |
| --- | --- |
| `manifests/us-ut-fep-official-documents.yaml` | `source_url` -> rule page; `request` block dropped; `html_content_selector` added; `rule_version_id`/`rule_type_id` recorded; dead `public_html_api_url`, `html_download`, `pdf_download` removed |
| `manifests/us-ut-fep-r986-239-official-document.yaml` | `source_url` -> rule page; `request` dropped; `html_content_selector` added beside the two anchor selectors |
| `manifests/us-ut-ssi-state-supplement-rules.yaml` | `source_url` -> rule page; `download_url` and `request` dropped; `html_content_selector` `body` -> `div[class$='_ruleHtml']` |
| `manifests/us-ut-benefits-w6-regulation.yaml` | same shape as the SSI row |
| `manifests/program-bundles/ssi.yaml` | the one R414-306 `source_url` row |
| `manifests/ssi-agent-queue.yaml` | `authority_scope.index_url` -> `POST /api/search`; the repair recorded in both note fields |
| `docs/ingest-runs/2026-10-06-w6-benefits-decisions.csv` | the two R994-401 `official_source_url` cells (CRLF preserved) |
| `scripts/build_ssi_state_supplement_manifests.py` | `build_ut_rule` rewritten onto the new API |
| `scripts/build_w6_benefits_manifests.py` | the R994-401 `doc(...)` row |

`html_content_selector: div[class$='_ruleHtml']` matches the suffix, not the whole class: the page wraps
the rule in a CSS-module class whose hash prefix changes per build (`eJUlaq_ruleHtml` on 2026-10-20). The
earlier `body` selector would now pull the page's own chrome into the block. A selector that does not match
raises, so a further layout change fails loudly instead of extracting the wrong root.

## Verification

Each scope was rebuilt from its repaired manifest into a scratch base at its own committed version string,
and compared row by row against the committed artifacts (fetched with `corpus fetch us-ut/regulation`).

| Scope | Coverage | Rows | Bodies |
| --- | --- | --- | --- |
| `2026-07-02-ut-fep-official-documents` | complete, 0 missing / 0 extra / 0 duplicate | 2 -> 2 | `block-1` 101,572 chars, identical |
| `2026-07-04-ut-fep-r986-239-r2026-07-17-dedup` | complete, 0 / 0 / 0 | 1 -> 2 (see below) | section `239` 594 chars, identical |
| `2026-09-15-ssi-state-supplement-rules` | complete, 0 / 0 / 0 | 2 -> 2 | section `6` 864 chars, identical |
| `2026-10-06-w6-benefits-regulation-ut` | complete, 0 / 0 / 0 | 2 -> 2 | `block-1` 17,930 chars, identical |

- **Every provision body is byte-identical to the committed one.** No citation path was added, dropped or
  duplicated in any scope, and no non-document row has an empty body.
- **Every deterministic provision `id` is unchanged** (for example the R414-306-6 section stays
  `f376a488-b9e9-5940-a6b5-2ff8796f3b7e`), so a re-stage keeps the existing Supabase row identity.
- `content-check` over the four rebuilt scopes: **0 findings** — no page navigation, no chrome-prefixed
  body, no hollow document root, no version picker. The `_ruleHtml` root keeps the Next.js chrome out.
- `scripts/validate_citation_paths.py` over the rebuilt provisions: 8 records, 7 unique paths,
  `RESULT: OK`; `block_n` 2, inside the baseline. The one repeat is the R986-200 document root discussed
  below.
- The anchor selectors were probed against the live pages before the rebuild: each of
  `R986-200-239.`, `R986-200-240.`, `R414-306-6.` and `KEY:` matches **exactly one** node inside the
  `_ruleHtml` root, as it did in the retained pre-relaunch source.
- Retained source bytes do change, because the snapshot is now the whole page rather than the Aspose-only
  file: FEP 2,548,146 -> 5,763,265; SSI 107,154 -> 360,661; W6 138,489 -> 429,341.

### Tests

`uv sync --extra dev` first, then, in this worktree and in a detached `HEAD` worktree with the same
`corpus fetch us-ut/regulation`:

```bash
AXIOM_CORPUS_PARTIAL_TESTS=1 uv run --extra dev pytest -q -m "not integration and not slow" \
  -k "manifest or official_documents or discovery or queue or content_check or citation"
AXIOM_CORPUS_PARTIAL_TESTS=1 uv run --extra dev pytest -q -m "not integration and not slow" \
  tests/test_local_file_urls.py tests/test_html_navigation_selectors.py \
  tests/test_html_navigation_blocks.py tests/test_corpus_documents.py \
  tests/test_concept_registry.py tests/test_corpus_storage.py
```

- Selection 1: **31 failed, 699 passed, 27 skipped** before and after, sorted `FAILED` lists byte-identical.
- Selection 2: **8 failed, 514 passed, 1 skipped** before and after, sorted `FAILED` lists byte-identical.
- No failure is new. Every one is a pre-existing `data/corpus` absence or fixture gap for an unrelated
  scope in a partial checkout (Armenia, BE, NY TANF, Wisconsin, Israel, SC, UK, CA, the AK/CT/MI/MT/ND/NY
  SNAP manuals, the TX/WA navigation-selector cases).
- `uv run ruff check` on both generator scripts: pass. Neither file was `ruff format`-clean before this
  change, so neither was reformatted; that would bury the repair in an unrelated diff.

## Findings

- **The R986-200-239 section body is truncated in the committed scope, and the rebuild reproduces the
  truncation exactly.** The committed body is 594 characters and stops mid-list at "(a) a work expense
  allowance of $100 for each person in the household unit who is employed;". The section between the
  `R986-200-239.` and `R986-200-240.` anchors is about 15,228 characters over 28 `div.awdiv` nodes.
  `_extract_anchor_range_html_block` walks `start.next_siblings` only, so the range ends where the start
  node's Aspose page container ends, part-way through the section. The pre-relaunch retained source has the
  same 660 `div.awdiv` nodes and the same 519..547 span, so this is **pre-existing and not caused by the
  relaunch or by this repair**. Left as it stands here, because fixing it changes a signed scope's content,
  which is a different work order. Recorded as a follow-up below.
- **The 239 scope's rebuild emits one row the committed scope does not hold:** the parent document row
  `us-ut/regulation/admin-rules/r986/200`, empty body, which the `r2026-07-17-dedup` pass removed because
  the 2026-07-02 whole-rule scope owns that citation. The extractor always writes a document root, so this
  is the normal pre-dedup output, not a repair artefact. `scripts/deduplicate_release_selector.py` now
  **refuses** to remove it ("removing a parent would orphan: us-ut/regulation/admin-rules/r986/200/239"),
  so the dedup that produced the committed scope cannot be replayed with the current script. Controller
  decision at re-sign time.
- **eRules v1.0.0 dropped `ruleFilingType`.** It is absent from the rule-version record and the rule page
  does not print it. The SSI generator would have written `rule_filing_type: null` and lost the
  `Nonsubstantive` value the pre-relaunch API gave on 2026-09-15, so that value is kept as the documented
  constant `UT_RULE_FILING_TYPE` rather than invented or dropped.
- **`update_queue_batch6` appended its note unguarded against a changed note string.** Carrying the repair
  inside `ROW_NOTES_6` duplicated the whole batch-6 paragraph on the next run. The repair text now lives in
  its own `REPAIR_NOTES_6` map, appended under the same `not in` guard batches 2 and 5 already use. Two
  consecutive generator runs now produce byte-identical files.
- **`scripts/build_w6_benefits_manifests.py` is not safe to re-run whole.** A full run reverts the
  2026-10-07 release-consolidation annotations that were hand-added to the Missouri rows of
  `docs/ingest-runs/2026-10-06-w6-benefits-decisions.csv` ("re-pointed from
  us-mo/regulation/2026-10-06-w6-benefits-regulation-mo … to the section-level carrier"), because the
  generator does not know about that consolidation. Those rows were restored, and the two Utah cells were
  repaired in place instead. Pre-existing; recorded as a follow-up.
- **`manifests/us-ut-tanf-ccdf-w6-regulation.yaml` is not affected.** The work order named it, but it
  carries no `adminrules.utah.gov` address: its source is the `jobs.utah.gov/occ/provider/r986700.pdf`
  PDF with Cornell LII discovery pointers, and its scope
  `us-ut/regulation/2026-10-06-w6-tanf-ccdf-regulation-ut` (20 rows, R986-700 pages 1-19) is unchanged.
  Left untouched.
- **`manifests/tax-agent-queue.yaml` was left alone.** Its two R865-9I rows (`primary_source_url` and
  `index_url`) still carry the dead `/public/rule/R865-9I/Current%20Rules` address on `main`; the repair
  lives on the open draft
  [TheAxiomFoundation/axiom-corpus#905](https://github.com/TheAxiomFoundation/axiom-corpus/pull/905)
  branch `discovery/ingest-w8-state-tax-regs`, together with
  `manifests/us-ut-income-tax-regulations.yaml`. Editing it here would conflict with that PR. After #905
  merges, no dead `adminrules.utah.gov` address is left in `manifests/`.
- Historical `docs/ingest-runs/` notes and `docs/coverage/` matrices keep the addresses that were live when
  they were written. They are records of past runs, so they were not rewritten.

## Controller

1. The repaired scopes need a re-fetch, a re-sign and a lock refresh:
   `us-ut/regulation/{2026-07-02-ut-fep-official-documents, 2026-07-04-ut-fep-r986-239-r2026-07-17-dedup,
   2026-09-15-ssi-state-supplement-rules, 2026-10-06-w6-benefits-regulation-ut}`. The provision bodies and
   ids do not move, so this is an address and provenance refresh, not a new expression.
2. `manifests/release-content-baseline.json` needs its reviewed update for those scopes at re-sign:
   `content-check --check-baseline` reports "provisions or inventory bytes changed" for each, while
   `findings` stays `[]`. No new finding needs recording.
3. Decide the 239 scope's document root: keep the pre-dedup two-row scope, or re-apply the dedup with a
   script that can drop a parent whose only child lives in the same scope.
4. Follow-up work orders, both out of scope here: the R986-200-239 anchor-range truncation, and making
   `build_w6_benefits_manifests.py` preserve hand-added decision-CSV annotations.
5. `data/corpus` artifacts stay uncommitted and unsigned. The rebuilds of this run were written to a
   scratch base; `corpus status us-ut/regulation` reports 20 present, 0 missing, 0 modified in the
   checkout.

Rebuild:

```bash
B=data/corpus   # the main checkout's corpus root
uv run axiom-corpus-ingest extract-official-documents --base $B \
  --version 2026-07-02-ut-fep-official-documents \
  --manifest manifests/us-ut-fep-official-documents.yaml
uv run axiom-corpus-ingest extract-official-documents --base $B \
  --version 2026-07-04-ut-fep-r986-239-r2026-07-17-dedup \
  --manifest manifests/us-ut-fep-r986-239-official-document.yaml
uv run axiom-corpus-ingest extract-official-documents --base $B \
  --version 2026-09-15-ssi-state-supplement-rules \
  --manifest manifests/us-ut-ssi-state-supplement-rules.yaml
uv run axiom-corpus-ingest extract-official-documents --base $B \
  --version 2026-10-06-w6-benefits-regulation-ut \
  --manifest manifests/us-ut-benefits-w6-regulation.yaml
```

Regenerate the two manifests from their generators (both idempotent for the Utah rows; the W6 caution
above applies to the rest of its output):

```bash
uv run python scripts/build_ssi_state_supplement_manifests.py --batch 6 --only ut
# W6: the R994-401 row only, then restore the Missouri decision-CSV annotations
uv run python scripts/build_w6_benefits_manifests.py
```
