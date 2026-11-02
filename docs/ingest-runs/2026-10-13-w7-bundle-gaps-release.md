# us-rulespec-2026-10-13-w7-bundle-gaps-union

Tenth release of the union lineage, cut from `us-rulespec-2026-10-12-w5-benefits-union` (published 2026-10-12,
activation requested in run 38335797295). It selects every scope of that cut and adds the 30 scopes of the wave-7
program-bundle gap ingests of 2026-10-12 (#834 state tax, #835 federal, #838 state benefits, landed by #839;
work orders `docs/coverage/program-bundle-gaps-2026-10-12/`): 2,558 rows. The bundles name about 85 documents that
only these scopes hold, among them the 30 title-26 sections of the plan parts of #836.

## Scopes added (30)

From docs/ingest-runs/2026-10-12-w7-federal.md, 7 scopes:

- `us/guidance/2026-10-12-w7-federal-guidance` (61 rows)
- `us/statute/2026-10-12-w7-federal-usc-closure-title-20` (165 rows)
- `us/statute/2026-10-12-w7-federal-usc-closure-title-25` (113 rows)
- `us/statute/2026-10-12-w7-federal-usc-closure-title-26` (439 rows)
- `us/statute/2026-10-12-w7-federal-usc-closure-title-29` (119 rows)
- `us/statute/2026-10-12-w7-federal-usc-closure-title-38` (89 rows)
- `us/statute/2026-10-12-w7-federal-usc-closure-title-8` (24 rows)

From docs/ingest-runs/2026-10-12-w7-state-tax.md, 2 scopes:

- `us-in/form/2026-10-12-w7-income-tax-forms-in` (10 rows)
- `us-va/statute/2026-10-12-w7-income-tax-statute-va` (801 rows)

From docs/ingest-runs/2026-10-12-w7-state-benefits.md, 18 scopes:

- `us-co/regulation/2026-10-12-w7-state-benefits-regulation-co` (140 rows)
- `us-dc/regulation/2026-10-12-w7-state-benefits-regulation-dc` (2 rows)
- `us-fl/statute/2026-10-12-w7-state-benefits-statute-fl` (2 rows)
- `us-il/guidance/2026-10-12-w7-state-benefits-guidance-il` (26 rows)
- `us-il/manual/2026-10-12-w7-state-benefits-manual-il` (98 rows)
- `us-il/policy/2026-10-12-w7-state-benefits-policy-il` (42 rows)
- `us-in/regulation/2026-10-12-w7-state-benefits-regulation-in` (116 rows)
- `us-ky/statute/2026-10-12-w7-state-benefits-statute-ky` (4 rows)
- `us-md/policy/2026-10-12-w7-state-benefits-policy-md` (42 rows)
- `us-mi/statute/2026-10-12-w7-state-benefits-statute-mi` (2 rows)
- `us-mn/manual/2026-10-12-w7-state-benefits-manual-mn` (10 rows)
- `us-mo/manual/2026-10-12-w7-state-benefits-manual-mo` (11 rows)
- `us-mo/policy/2026-10-12-w7-state-benefits-policy-mo` (42 rows)
- `us-nc/guidance/2026-10-12-w7-state-benefits-guidance-nc` (3 rows)
- `us-nj/rulemaking/2026-10-12-w7-state-benefits-rulemaking-nj` (21 rows)
- `us-nj/statute/2026-10-12-w7-state-benefits-statute-nj` (2 rows)
- `us-wa/rulemaking/2026-10-12-w7-state-benefits-rulemaking-wa` (4 rows)
- `us-wy/guidance/2026-10-12-w7-state-benefits-guidance-wy` (9 rows)

From this note (below), 3 scopes:

- `us-pa/regulation/2026-10-12-w7-state-benefits-regulation-pa-title-34-chapter-65-r2026-10-13-without-shared-containers` (80 rows)
- `us-pa/regulation/2026-10-12-w7-state-benefits-regulation-pa-title-55-chapter-177-r2026-10-13-without-shared-containers` (16 rows)
- `us-pa/regulation/2026-10-12-w7-state-benefits-regulation-pa-title-55-chapter-178-r2026-10-13-without-shared-containers` (65 rows)
Every added scope has a coverage file with `complete: true`.

## Pennsylvania Code: successors without the shared container rows

The three Pennsylvania Code scopes of the state-benefits run (34 Pa. Code ch. 65, 55 Pa. Code ch. 177 and ch. 178) each
emit the `us-pa/regulation` root, which the selected
`us-pa/regulation/2026-09-14-income-tax-regulations-title-61-chapter-101-…-125` scope already carries, and chapters 177
and 178 both emit `us-pa/regulation/title-55`. Their successors keep every other row: chapter 65 and chapter 177 drop
the root; chapter 178 drops the root and `title-55`, which the chapter 177 successor keeps. Release validation checks
parent links within a scope, so each successor's top row is then detached with `scripts/self_contain_usc_scope.py`
(the dropped parent is recorded as `detached_parent_citation_path`), as the released `-self-contained` scopes were:

```bash
B=$PWD/data/corpus
for v in 2026-10-12-w7-state-benefits-regulation-pa-title-34-chapter-65 \
         2026-10-12-w7-state-benefits-regulation-pa-title-55-chapter-177 \
         2026-10-12-w7-state-benefits-regulation-pa-title-55-chapter-178; do
  drop='^us-pa/regulation$'; [ "${v##*-}" = 178 ] && drop='^us-pa/regulation(/title-55)?$'
  ARGS=(); for p in $(jq -r .citation_path $B/provisions/us-pa/regulation/$v.jsonl | grep -vE "$drop"); do
    ARGS+=(--include-citation-from "$v=$p"); done
  uv run --extra dev python scripts/consolidate_release_scopes.py --base $B --jurisdiction us-pa \
    --document-class regulation --source-version $v "${ARGS[@]}" \
    --target-version $v-r2026-10-13-without-shared-containers
  uv run --extra dev python scripts/self_contain_usc_scope.py --base $B --jurisdiction us-pa \
    --document-class regulation --version $v-r2026-10-13-without-shared-containers
done
```

The three original scopes are not selected.

## Notes

- Colorado 8 CCR 1403-1: the current edition (ruleVersionId 12658, effective 2026-08-14) is in
  `us-co/regulation/2026-10-12-w7-state-benefits-regulation-co` at the dated sibling path
  `us-co/regulation/8-ccr-1403-1-eff-2026-08-14`, beside the served 2023 edition; a later section-level build can
  replace both (the Colorado swap left open on #819).
- Minnesota: four Combined Manual and ESM pages fetched with the documented `chrome120` profile were extracted from the
  retained official bytes (`local_path`); their inventory names the local file, and the run note records their
  SHA-256. Twelve Minnesota rows stay OUTREACH (Radware).

## Not selected

- `us-me/form/2026-10-12-w7-income-tax-forms-me`: withdrawn by the state-tax agent (the forms are held on the open #754).
- The scopes held out for their owner in the last three cuts (CMS-2454 FR, MN inflation amounts, the MO page-level
  duplicate), the changes of the draft #819 and the Colorado sections of #813, and the D.C. and Maine scopes of the open
  #753 and #754.

## Checks

- No citation path in two selected scopes: 408,541 paths over 1,567 scopes, 0 duplicates.
- `validate-release --ignore-r2-missing`: ok, 1,567 scopes, 0 errors, 564 warnings (the same count as the
  `us-rulespec-2026-10-12-w5-benefits-union` cut).
- Citation-path ratchets over every locked provisions file plus the 30 scopes (2,428 files): `block_n` 85,421 → 85,559
  (+138), `page_n` 177,867 → 178,885 (+1,018, mostly the Virginia act stored one row per page), `uppercase_segments`
  18,796 → 19,332 (+536, U.S. Code subparagraph and section designations such as `(A)` and `25F`); the other families
  unchanged.
- `guard-ingested`: every changed corpus artifact has a signed ingest manifest. `corpus verify --attest`: 2,428 lock
  files, 63,366 entries, OK.
- `corpus push --changed-since origin/main`: 144 objects uploaded (57.9 MB), 5 already in R2; `corpus verify --remote`:
  0 missing.

## Activation

The release carries every pair of `us-rulespec-2026-10-12-w5-benefits-union`. Activate it after that cut; if it is
activated first, it also carries that cut's 68 scopes, so the monotonicity gate accepts it over the active
`us-rulespec-2026-10-11-w5-remainder-union` as well.

## What the signer runs next

1. With a clean tracked tree, sign and lock the 30 scopes of `docs/ingest-runs/2026-10-13-w7-bundle-gaps-unsigned-scopes.tsv`
   (`sign-ingest-manifest --jurisdiction J --document-class C --version V --command "rebuild: see <run_note>" --lock`).
2. `corpus push --changed-since origin/main`, then `corpus verify --remote --changed-since origin/main`.
3. Raise the citation-path ratchets (`scripts/validate_citation_paths.py --update-baselines` over the full tree) and
   commit the selector; `guard-ingested` and `corpus verify --attest`; open the pull request.
4. After the merge, `publish.yml` runs on the new selector; then the activation preview and the protected activation.
