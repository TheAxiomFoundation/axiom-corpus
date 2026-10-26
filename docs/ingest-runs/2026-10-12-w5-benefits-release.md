# us-rulespec-2026-10-12-w5-benefits-union

Ninth release of the union lineage, after `us-rulespec-2026-10-11-w5-remainder-union` (active since 2026-10-12
18:12 UTC). It selects every scope of that cut and adds 68 scopes of the wave-5 benefit runs of 2026-09-15, ingested on
pull requests merged 2026-10-12 (#714 Medicaid/CHIP, #715 SNAP/WIC, #718 SSI/LIHEAP/Medicare) but never released.
The program bundles name 201 documents that only these scopes hold (the bundle collector run of 2026-10-12 17:20 UTC;
`docs/coverage/program-bundle-gaps-2026-10-12/release-scopes.tsv`): by bundle, Medicaid 195, Medicare 10, CHIP 4,
SSI 3, LIHEAP 1 and WIC 1, of which the Wyoming Medicaid eligibility manual closure holds 121.

## Scopes added (68)

From docs/ingest-runs/2026-09-15-medicaid-chip.md (#714), 62 scopes:

- `2026-09-15-medicaid-magi-verification-plan` (policy) of 51 jurisdictions: AK, AL, AR, AZ, CA, CO, CT, DC, DE, FL, GA, HI, IA, ID, IL, IN, KS, KY, LA, MA, MD, ME, MI, MN, MO, MS, MT, NC, ND, NE, NH, NJ, NM, NV, NY, OH, OK, OR, PA, RI, SC, SD, TN, TX, UT, VA, VT, WA, WI, WV, WY
- `2026-09-15-medicaid-1115-stc` (policy) of KY, MT, PA, SD, VA, WI, WY
- `2026-09-15-chip-income-premium-table-2026` (policy) of ME, SC
- `us-id/policy/2026-09-15-medicaid-income-table-2026`
- `us-wy/manual/2026-09-15-medicaid-eligibility-manual-closure`

From docs/ingest-runs/2026-09-15-snap-wic.md (#715), 1 scope:

- `us-tn/regulation/2026-09-15-wic-state-regulation`

From docs/ingest-runs/2026-09-15-ssi-liheap-medicare.md (#718), 5 scopes:

- `us/guidance/2026-09-15-liheap-model-plan`
- `us/manual/2026-09-15-medicare-cms-iom-100-03`
- `us/manual/2026-09-15-medicare-cms-iom-100-05`
- `us/manual/2026-09-15-ssi-poms-si-00529`
- `us-ut/regulation/2026-09-15-ssi-state-supplement-rules`

Every added scope has a coverage file with `complete: true`. None needs a successor: no citation path of an added scope
is in a selected scope, and no two added scopes share a path.

## Not selected

- The three scopes held out for the owner in the last two cuts, though the bundles name one document in each:
  `us/rulemaking/2026-06-03-cms-2454-ifc-...` (the CMS-2454 FR scope),
  `us-mn/guidance/2026-07-22-mn-income-tax-inflation-adjusted-amounts-2026` and
  `us-mo/regulation/2026-10-06-w6-benefits-regulation-mo` (the page-level duplicate of the selected section-level scope).
- The changes of the draft TheAxiomFoundation/axiom-corpus#819 (`us-rulespec-2026-10-12-w6-successor-union`: the two
  NSF scopes and the South Carolina chapter 6 successor of #760), and the Colorado 8 CCR 1403-1 sections of #813: they
  are their owner's cut.
- The wave-7 ingests of 2026-10-12 (draft PRs, not on `main`).

## Checks

- No citation path in two selected scopes: the 68 added scopes hold 3,066 paths, none of them in a scope of the active
  cut and none in two added scopes.
- `validate-release --ignore-r2-missing`: ok, 1,537 scopes, 0 errors, 564 warnings (the same 564 as the active cut).
- Citation-path ratchets over every locked provisions file plus the 68 scopes (2,398 files): `block_n` 84,985 → 85,421
  (+436), `page_n` 176,322 → 177,867 (+1,545), all from the 68 scopes (the MAGI verification plans and the section 1115
  terms are PDFs stored one row per page); the other families unchanged.
- `guard-ingested`: every changed corpus artifact has a signed ingest manifest. `corpus verify --attest`: 2,398 lock
  files, 63,214 entries, OK.
- `corpus push --changed-since origin/main`: 411 objects uploaded (93.8 MB), 2 already in R2; `corpus verify --remote`:
  0 missing.

## Activation

The release carries every pair of the active cut, so its takeover displaces only
`us-rulespec-2026-10-11-w5-remainder-union`. TheAxiomFoundation/axiom-corpus#819 is cut from
`us-rulespec-2026-10-07-w6-bundle-gaps-union`: whichever of the two activates second must carry the other's added
scopes, or the monotonicity gate refuses it.

## What the signer runs next

1. With a clean tracked tree, sign and lock the 68 scopes of `docs/ingest-runs/2026-10-12-w5-benefits-unsigned-scopes.tsv`
   (`sign-ingest-manifest --jurisdiction J --document-class C --version V --command "rebuild: see <run_note>" --lock`).
2. `corpus push --changed-since origin/main`, then `corpus verify --remote --changed-since origin/main`.
3. Raise the citation-path ratchets (`scripts/validate_citation_paths.py --update-baselines` over the full tree) and
   commit the selector; `guard-ingested` and `corpus verify --attest`; open the pull request.
4. After the merge, `publish.yml` runs on the new selector; then the activation preview and the protected activation.
