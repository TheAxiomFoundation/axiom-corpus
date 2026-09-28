# Wave-4 release consolidation: draft selector us-rulespec-2026-09-14-wave4-union

Date: 2026-09-14
Controller pass that turns the five wave-4 ingestion runs of 2026-09-14 (branch `discovery/fourth-run-union`,
PR #706, the union of `discovery/ingest-msp-charts-snap-fy2026`, `discovery/ingest-liheap-matrix-ssi-standards`,
`discovery/ingest-state-tax-statute-ty2026`, `discovery/ingest-tanf-whole-manuals-md-comar` and
`discovery/ingest-state-tax-regulations`) into the fifth US selector after
`manifests/releases/us-rulespec-2026-09-13-cms-state-plans-union.json` (863 scopes). Everything here is local and
unsigned; the artifacts live under `/Users/pavelmakarchuk/axiom-corpus/data/corpus` on the controller's machine only.

Draft selector: `docs/ingest-runs/2026-09-14-us-rulespec-wave4-union.selector.json`
(`us-rulespec-2026-09-14-wave4-union`, quality profile `complete-expression-dates-v1`, **1,042 scopes**). It is kept
outside `manifests/releases/` on purpose, as the 2026-09-11 and 2026-09-13 drafts were: CI deep-validates every tracked
selector against the checked-in `data/corpus`, so it can only be tracked on the release branch after the artifact
commit (`scripts/sign_release_scopes.sh`).

The authoritative inputs are the Controller tables of the five run notes; the four per-note `*.selector.json` drafts
(each the 761-scope 2026-09-13 federal-and-plans union plus that run's changes) were cross-checked against the result:
every scope a draft adds is selected (or replaced by its consolidated successor, below) and every scope a draft removes
is absent. Every selected scope has a coverage file on disk with `complete: true` (checked by script, 1,042 files).
No library function was modified in this pass (no impact analysis to run; the GitNexus MCP tools were not in this
session's tool list), and no manifest was needed: the consolidations read and write corpus artifacts only.

## Arithmetic

863 (fourth cut) + 203 additions - 24 removals = 1,042.

| Run note | Added | Removed | Notes |
| --- | ---: | ---: | --- |
| `2026-09-14-msp-charts-snap-fy2026.md` | 49 | 0 | 27 MSP income/resource-standard scopes, 22 SNAP FY 2026 transmittal scopes |
| `2026-09-14-liheap-matrix-ssi-standards.md` | 66 | 0 | 55 LIHEAP + 10 SSI scopes, plus `us-ks/statute/2026-07-04-ks-sspp-statute` (K.S.A. 39-972, on disk since July, `complete: true`, 2 rows under `us-ks/statute/39/972/supplemental-income`, no path shared with any other us-ks scope on disk) for SSI-ST-2 as the note asks |
| `2026-09-14-state-tax-statute-ty2026.md` | 48 | 19 | 19 whole-chapter statute scopes in (AL, AZ, CA, CT x2, DE, ID, KY, MD, ME, MI, MN x3, NE, NY, OH, UT, VA), 29 TY2026 indexed-amount scopes in; 18 released statute scopes and the defective `us-mn/guidance/2026-07-22-mn-income-tax-inflation-adjusted-amounts-2026` out |
| `2026-09-14-tanf-whole-manuals-md-comar.md` | 3 | 2 | CT UPM and GA TANF whole manuals swap the July slices out; DE DSSM 3000 added; the Maryland swap is folded into the consolidation below |
| `2026-09-14-state-tax-regulations.md` | 37 | 3 | 34 regulation scopes selected as extracted; MD, OH, OR selected through consolidated successors that replace the released scope they collided with |

## Consolidations

The three tax-regulation scopes of Maryland, Ohio and Oregon emit the adapter's root container row (`us-md/regulation`,
`us-oh/regulation`, `us-or/regulation`) that a released scope of the same jurisdiction already carries, and a selector
cannot carry a path twice. Same mechanism and command shape as `docs/ingest-runs/2026-09-11-release-consolidation.md`
and the July `-r2026-07-17-dedup` re-versions: `scripts/consolidate_release_scopes.py` builds one immutable scope from
ordered sources (released scope first), folds byte-identical body-less container rows into one row, and refuses any
conflicting text. Released scopes stay untouched; the selector swaps them for their successors. Run from the worktree
with `--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`.

Maryland takes three sources at once: the released COMAR 07.03 chapters 06-07 scope, the July TCA chapter-03 scope that
the TANF note swaps in (its own `...-r2026-09-14-chapter-03-consolidated` successor, 58 rows, already on disk), and the
new COMAR 03.04 income-tax scope. One successor absorbs both the TANF note's swap and the tax note's root collision, so
the TANF note's two-source successor is superseded and not selected.

```bash
P=/Users/pavelmakarchuk/axiom-corpus/.venv/bin/python; B=/Users/pavelmakarchuk/axiom-corpus/data/corpus
$P scripts/consolidate_release_scopes.py --base $B \
  --jurisdiction us-md --document-class regulation \
  --source-version 2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07 \
  --source-version 2026-07-03-md-tca-comar-publication-2026-06-29-title-07-subtitle-03-chapter-03 \
  --source-version 2026-09-14-income-tax-regulations-publication-2026-09-11-title-03-subtitle-04 \
  --target-version 2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07-r2026-09-14-chapter-03-title-03-subtitle-04-consolidated

$P scripts/consolidate_release_scopes.py --base $B \
  --jurisdiction us-oh --document-class regulation \
  --source-version 2026-07-16-agency-5101-4-r2026-09-11-5101-1-5122-36-consolidated \
  --source-version 2026-09-14-income-tax-regulations-agency-5703-chapter-5703-7 \
  --target-version 2026-07-16-agency-5101-4-r2026-09-11-5101-1-5122-36-r2026-09-14-5703-7-consolidated

$P scripts/consolidate_release_scopes.py --base $B \
  --jurisdiction us-or --document-class regulation \
  --source-version 2026-09-10-tanf-state-policy-manual-chapter-461 \
  --source-version 2026-09-14-income-tax-regulations-chapter-150-division-316 \
  --target-version 2026-09-10-tanf-state-policy-manual-chapter-461-r2026-09-14-150-316-consolidated
```

| Consolidated scope | Sources (rows) | Rows | Folded |
| --- | --- | ---: | --- |
| `us-md/regulation/2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07-r2026-09-14-chapter-03-title-03-subtitle-04-consolidated` | 30 (chapters 06-07, released) + 31 (chapter 03) + 109 (03.04) | 166 | 4: `us-md/regulation` carried by all three sources (two copies folded), `title-07` and `title-07/subtitle-03` carried by the two 07.03 sources (one copy each) |
| `us-oh/regulation/2026-07-16-agency-5101-4-r2026-09-11-5101-1-5122-36-r2026-09-14-5703-7-consolidated` | 169 (released) + 17 (5703-7) | 185 | 1: `us-oh/regulation` |
| `us-or/regulation/2026-09-10-tanf-state-policy-manual-chapter-461-r2026-09-14-150-316-consolidated` | 571 (released) + 148 (150-316) | 718 | 1: `us-or/regulation` |

Checked after writing (script over the JSONL): every consolidated scope's coverage is `complete: true` with 0 missing,
0 extra, 0 duplicate citation paths; every row of every source is present in its successor with a byte-equal body; no
`--prefer-duplicate-carrier` was needed because no two sources share a text-bearing path. The sources directory of each
successor carries every input's files under `sources/<jur>/regulation/<target>/<source-version>/...`.

## Swaps (released scope out, successor in)

| Jurisdiction / class | Out | In | Cited paths |
| --- | --- | --- | --- |
| us-ct / policy | `2026-07-02-ct-ssp-upm-and-standards` (28 rows) | `2026-09-14-tanf-manual-whole` | all 28 carried, byte-equal (TANF note) |
| us-ga / manual | `2026-06-25-ga-tanf` (47 rows) | `2026-09-14-tanf-manual-whole` | all 47 carried, byte-equal (TANF note) |
| us-md / regulation | `2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07` (30 rows) | `...chapters-06-07-r2026-09-14-chapter-03-title-03-subtitle-04-consolidated` | all 30 carried, byte-equal |
| us-oh / regulation | `2026-07-16-agency-5101-4-r2026-09-11-5101-1-5122-36-consolidated` (169 rows) | `...-r2026-09-14-5703-7-consolidated` | all 169 carried, byte-equal |
| us-or / regulation | `2026-09-10-tanf-state-policy-manual-chapter-461` (571 rows) | `...-r2026-09-14-150-316-consolidated` | all 571 carried, byte-equal |
| 18 statute scopes + 1 guidance scope | the tax statute note's `remove` rows | the whole-chapter and TY2026 scopes | see below |

## On disk, not selected

No scope is held out of this cut for a collision: every `duplicate_release_citation` the per-note drafts reported is
resolved by the three consolidations above. Scopes that stay on disk for provenance and are neither selected nor to be
signed:

- `us-md/regulation/2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07-r2026-09-14-chapter-03-consolidated`
  (the TANF note's two-source successor, 58 rows): superseded by the three-source successor.
- `us-md/regulation/2026-07-03-md-tca-comar-publication-2026-06-29-title-07-subtitle-03-chapter-03` (31 rows, held out
  since 2026-09-11): now carried by the three-source successor.
- `us-md/regulation/2026-09-14-income-tax-regulations-publication-2026-09-11-title-03-subtitle-04`,
  `us-oh/regulation/2026-09-14-income-tax-regulations-agency-5703-chapter-5703-7`,
  `us-or/regulation/2026-09-14-income-tax-regulations-chapter-150-division-316`: the consolidation inputs.
- The 24 removed scopes: the released ones stay in earlier releases' history; the queue rows and run notes still name
  the extraction run ids, the selector is the release truth.
- As before, the pointer, blocked and needs-review rows of the five notes add nothing (NY OTDA, AZ DES, UT, WY, DC, NJ,
  AR, DE tax regulations, and the rest listed there).

## Dangling rulespec-us citations

The tax statute note (commit c8951033 of `~/rulespec-us`) lists sub-section rows of the swapped-out recovery scopes that
rulespec-us cites and that exist in neither the new chapter scope nor a kept scope. They are recorded here only; the
re-point to the section root (with anchors for the CA paragraph) is a rulespec-us follow-up, not a corpus change. Full
citation paths, confirmed absent from every selected scope of the jurisdiction:

- `us-ca/statute/wic/11450/a/1/A`
- `us-ct/statute/12-700/block-1`, `us-ct/statute/12-704i/block-1`
- `us-me/statute/36/5111/block-2`
- `us-mi/statute/206.30/2`, `us-mi/statute/206.30/3`, `us-mi/statute/206.30/7`, `us-mi/statute/206.30/8`,
  `us-mi/statute/206.30/10`, `us-mi/statute/206.30/11`, `us-mi/statute/206.30/12`, `us-mi/statute/206.51/1`,
  `us-mi/statute/206.51/6`, `us-mi/statute/206.51/10`
- `us-mn/statute/290.06/block-12`, `us-mn/statute/290.06/block-13`

## Citation paths of swapped-out scopes that no selected scope carries

Computed over the provisions JSONL of all 1,042 selected scopes: 205 paths in 10 of the 24 removed scopes, every one a
`block-N` sub-row or `/N` subsection split of the July recovery extractions (plus the MI `recovery/us-mi-code-*`
document rows and the five rows of the defective MN inflation-adjusted-amounts scope, replaced by the re-taken PDF under
`us-mn/guidance/.../ty2026/...`); the section roots are all in the new chapter scopes. The other 14 removed scopes
(AL, CA core sections, DE, ID, KY, NY x2, UT, VA statute; CT policy; GA manual; MD, OH, OR regulation) are carried in
full.

`us-az/statute/2026-07-13-recovery` (7 of 14 rows):

- `us-az/statute/43-1011/block-1`
- `us-az/statute/43-1023/block-1`
- `us-az/statute/43-1041/block-1`
- `us-az/statute/43-1072/block-1`
- `us-az/statute/43-1072.01/block-1`
- `us-az/statute/43-1073/block-1`
- `us-az/statute/43-1073.01/block-1`

`us-ca/statute/2026-07-13-recovery` (23 of 33 rows):

- `us-ca/statute/rtc/17014/block-1`
- `us-ca/statute/rtc/17014/block-2`
- `us-ca/statute/rtc/17062.1/block-1`
- `us-ca/statute/rtc/17062.1/block-2`
- `us-ca/statute/rtc/17016/block-1`
- `us-ca/statute/rtc/17016/block-2`
- `us-ca/statute/rtc/17017/block-1`
- `us-ca/statute/rtc/17017/block-2`
- `us-ca/statute/rtc/17029/block-1`
- `us-ca/statute/rtc/17029/block-2`
- `us-ca/statute/rtc/17034/block-1`
- `us-ca/statute/rtc/17034/block-2`
- `us-ca/statute/rtc/17038/block-1`
- `us-ca/statute/rtc/17038/block-2`
- `us-ca/statute/rtc/17053.6/block-1`
- `us-ca/statute/rtc/17053.6/block-2`
- `us-ca/statute/rtc/17054.7/block-1`
- `us-ca/statute/rtc/17054.7/block-2`
- `us-ca/statute/rtc/17061/block-1`
- `us-ca/statute/rtc/17061/block-2`
- `us-ca/statute/wic/11450/a/1/A`
- `us-ca/statute/wic/11450/a/1/A/block-1`
- `us-ca/statute/wic/11450/a/1/A/block-2`

`us-ct/statute/2026-07-13-recovery` (9 of 15 rows):

- `us-ct/statute/12-700/block-1`
- `us-ct/statute/12-704e/block-1`
- `us-ct/statute/12-704i/block-1`
- `us-ct/statute/17b-104/block-1`
- `us-ct/statute/17b-104/block-2`
- `us-ct/statute/17b-112/block-1`
- `us-ct/statute/17b-112/block-2`
- `us-ct/statute/17b-600/block-1`
- `us-ct/statute/17b-600/block-2`

`us-md/statute/2026-07-13-recovery-r2026-07-24-immutable` (2 of 4 rows):

- `us-md/statute/gtg/10-105/block-1`
- `us-md/statute/gtg/10-211/block-1`

`us-me/statute/2026-07-13-recovery` (7 of 13 rows):

- `us-me/statute/36/5111/block-1`
- `us-me/statute/36/5111/block-2`
- `us-me/statute/36/5124-C/block-1`
- `us-me/statute/36/5126-A/block-1`
- `us-me/statute/36/5213-A/block-1`
- `us-me/statute/36/5219-S/block-1`
- `us-me/statute/36/5219-SS/block-1`

`us-mi/statute/2026-07-13-recovery` (14 of 15 rows):

- `us-mi/statute/recovery/us-mi-code-206.30`
- `us-mi/statute/recovery/us-mi-code-206.30/block-1`
- `us-mi/statute/206.30/10`
- `us-mi/statute/206.30/11`
- `us-mi/statute/206.30/12`
- `us-mi/statute/206.30/2`
- `us-mi/statute/206.30/3`
- `us-mi/statute/206.30/7`
- `us-mi/statute/206.30/8`
- `us-mi/statute/recovery/us-mi-code-206.51`
- `us-mi/statute/recovery/us-mi-code-206.51/block-1`
- `us-mi/statute/206.51/1`
- `us-mi/statute/206.51/10`
- `us-mi/statute/206.51/6`

`us-mn/statute/2026-07-13-recovery` (120 of 125 rows):

- `us-mn/statute/290.0121/block-1`
- `us-mn/statute/290.0121/block-2`
- `us-mn/statute/290.0121/block-3`
- `us-mn/statute/290.0121/block-4`
- `us-mn/statute/290.0121/block-5`
- `us-mn/statute/290.0121/block-6`
- `us-mn/statute/290.0121/block-7`
- `us-mn/statute/290.0121/block-8`
- `us-mn/statute/290.0121/block-9`
- `us-mn/statute/290.0121/block-10`
- `us-mn/statute/290.0123/block-1`
- `us-mn/statute/290.0123/block-2`
- `us-mn/statute/290.0123/block-3`
- `us-mn/statute/290.0123/block-4`
- `us-mn/statute/290.0123/block-5`
- `us-mn/statute/290.0123/block-6`
- `us-mn/statute/290.0123/block-7`
- `us-mn/statute/290.0123/block-8`
- `us-mn/statute/290.0123/block-9`
- `us-mn/statute/290.0123/block-10`
- `us-mn/statute/290.0123/block-11`
- `us-mn/statute/290.0123/block-12`
- `us-mn/statute/290.0123/block-13`
- `us-mn/statute/290.06/block-1`
- `us-mn/statute/290.06/block-2`
- `us-mn/statute/290.06/block-3`
- `us-mn/statute/290.06/block-4`
- `us-mn/statute/290.06/block-5`
- `us-mn/statute/290.06/block-6`
- `us-mn/statute/290.06/block-7`
- `us-mn/statute/290.06/block-8`
- `us-mn/statute/290.06/block-9`
- `us-mn/statute/290.06/block-10`
- `us-mn/statute/290.06/block-11`
- `us-mn/statute/290.06/block-12`
- `us-mn/statute/290.06/block-13`
- `us-mn/statute/290.06/block-14`
- `us-mn/statute/290.06/block-15`
- `us-mn/statute/290.06/block-16`
- `us-mn/statute/290.06/block-17`
- `us-mn/statute/290.06/block-18`
- `us-mn/statute/290.06/block-19`
- `us-mn/statute/290.06/block-20`
- `us-mn/statute/290.06/block-21`
- `us-mn/statute/290.06/block-22`
- `us-mn/statute/290.06/block-23`
- `us-mn/statute/290.06/block-24`
- `us-mn/statute/290.06/block-25`
- `us-mn/statute/290.06/block-26`
- `us-mn/statute/290.06/block-27`
- `us-mn/statute/290.06/block-28`
- `us-mn/statute/290.06/block-29`
- `us-mn/statute/290.06/block-30`
- `us-mn/statute/290.06/block-31`
- `us-mn/statute/290.06/block-32`
- `us-mn/statute/290.06/block-33`
- `us-mn/statute/290.06/block-34`
- `us-mn/statute/290.06/block-35`
- `us-mn/statute/290.06/block-36`
- `us-mn/statute/290.06/block-37`
- `us-mn/statute/290.06/block-38`
- `us-mn/statute/290.06/block-39`
- `us-mn/statute/290.06/block-40`
- `us-mn/statute/290.06/block-41`
- `us-mn/statute/290.06/block-42`
- `us-mn/statute/290.06/block-43`
- `us-mn/statute/290.06/block-44`
- `us-mn/statute/290.06/block-45`
- `us-mn/statute/290.06/block-46`
- `us-mn/statute/290.06/block-47`
- `us-mn/statute/290.06/block-48`
- `us-mn/statute/290.06/block-49`
- `us-mn/statute/290.06/block-50`
- `us-mn/statute/290.06/block-51`
- `us-mn/statute/290.06/block-52`
- `us-mn/statute/290.06/block-53`
- `us-mn/statute/290.06/block-54`
- `us-mn/statute/290.06/block-55`
- `us-mn/statute/290.06/block-56`
- `us-mn/statute/290.06/block-57`
- `us-mn/statute/290.06/block-58`
- `us-mn/statute/290.06/block-59`
- `us-mn/statute/290.06/block-60`
- `us-mn/statute/290.06/block-61`
- `us-mn/statute/290.06/block-62`
- `us-mn/statute/290.06/block-63`
- `us-mn/statute/290.06/block-64`
- `us-mn/statute/290.06/block-65`
- `us-mn/statute/290.06/block-66`
- `us-mn/statute/290.067/block-1`
- `us-mn/statute/290.067/block-2`
- `us-mn/statute/290.067/block-3`
- `us-mn/statute/290.067/block-4`
- `us-mn/statute/290.067/block-5`
- `us-mn/statute/290.067/block-6`
- `us-mn/statute/290.067/block-7`
- `us-mn/statute/290.067/block-8`
- `us-mn/statute/290.067/block-9`
- `us-mn/statute/290.067/block-10`
- `us-mn/statute/290.067/block-11`
- `us-mn/statute/290.067/block-12`
- `us-mn/statute/290.067/block-13`
- `us-mn/statute/290.067/block-14`
- `us-mn/statute/290.067/block-15`
- `us-mn/statute/290.0671/block-1`
- `us-mn/statute/290.0671/block-2`
- `us-mn/statute/290.0671/block-3`
- `us-mn/statute/290.0671/block-4`
- `us-mn/statute/290.0671/block-5`
- `us-mn/statute/290.0671/block-6`
- `us-mn/statute/290.0671/block-7`
- `us-mn/statute/290.0671/block-8`
- `us-mn/statute/290.0671/block-9`
- `us-mn/statute/290.0671/block-10`
- `us-mn/statute/290.0671/block-11`
- `us-mn/statute/290.0671/block-12`
- `us-mn/statute/290.0671/block-13`
- `us-mn/statute/290.0671/block-14`
- `us-mn/statute/290.0671/block-15`
- `us-mn/statute/290.0671/block-16`

`us-ne/statute/2026-07-13-recovery` (10 of 13 rows):

- `us-ne/statute/77/77-2715.03/block-1`
- `us-ne/statute/77/77-2715.03/block-2`
- `us-ne/statute/77/77-2715.03/block-3`
- `us-ne/statute/77/77-2715.07/block-1`
- `us-ne/statute/77/77-2715.07/block-2`
- `us-ne/statute/77/77-2715.07/block-3`
- `us-ne/statute/77/77-2715.07/block-4`
- `us-ne/statute/77/77-2716.01/block-1`
- `us-ne/statute/77/77-2716.01/block-2`
- `us-ne/statute/77/77-2716.01/block-3`

`us-oh/statute/2026-07-13-recovery` (8 of 12 rows):

- `us-oh/statute/5747.02/block-1`
- `us-oh/statute/5747.02/block-2`
- `us-oh/statute/5747.025/block-1`
- `us-oh/statute/5747.025/block-2`
- `us-oh/statute/5747.71/block-1`
- `us-oh/statute/5747.71/block-2`
- `us-oh/statute/5747.98/block-1`
- `us-oh/statute/5747.98/block-2`

`us-mn/guidance/2026-07-22-mn-income-tax-inflation-adjusted-amounts-2026` (5 of 5 rows):

- `us-mn/guidance/department-of-revenue/inflation-adjusted-amounts/2026/income-tax-brackets`
- `us-mn/guidance/department-of-revenue/inflation-adjusted-amounts/2026/income-tax-brackets/married-joint-or-surviving-spouse`
- `us-mn/guidance/department-of-revenue/inflation-adjusted-amounts/2026/income-tax-brackets/married-separate`
- `us-mn/guidance/department-of-revenue/inflation-adjusted-amounts/2026/income-tax-brackets/single`
- `us-mn/guidance/department-of-revenue/inflation-adjusted-amounts/2026/income-tax-brackets/head-of-household`

## Validation

```
/Users/pavelmakarchuk/axiom-corpus/.venv/bin/axiom-corpus-ingest validate-release \
  --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
  --release docs/ingest-runs/2026-09-14-us-rulespec-wave4-union.selector.json --ignore-r2-missing --max-issues 40
```

`ok: true`, `scope_count: 1042`, `error_count: 0`, `warning_count: 546` (68 s). With `--max-issues 600` the warnings
are the 546 pre-existing ones: 541 `missing_parent_id` in the released `us-ca/regulation/2026-07-13-recovery` and the
5 advisory `unsectioned_document_body` warnings on single-body documents (`us-ga/manual`, `us-ky/manual`,
`us-md/manual`, `us-or/manual` WIC policy manuals and `us-ia/form` TY2025 forms, all `2026-09-10` scopes). No
`duplicate_release_citation` remains. `ruff check .` passes.

## Controller commands from here

1. Merge PR #706 (`discovery/fourth-run-union`) to `main` and cut a release branch from it.
2. In that shell only, export `AXIOM_CORPUS_INGEST_PRIVATE_KEY`; `sign-ingest-manifest` the 203 scopes this cut adds
   (199 wave-4 extractions, the July K.S.A. 39-972 scope, the 3 consolidated successors; not the on-disk inputs
   listed above).
3. `scripts/sign_release_scopes.sh docs/ingest-runs/2026-09-14-us-rulespec-wave4-union.selector.json manifests/releases/us-rulespec-2026-09-13-cms-state-plans-union.json`
   commits the artifacts, tracks the selector and deep-validates it; then `publish_corpus.py --dry-run` and the
   protected activation flow.
