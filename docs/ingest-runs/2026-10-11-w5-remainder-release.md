# us-rulespec-2026-10-11-w5-remainder-union

Eighth release of the union lineage, after `us-rulespec-2026-10-07-w6-bundle-gaps-union` (active since 2026-10-08).
It selects every scope of that cut and adds 24 scopes of the wave-5 runs of 2026-09-15 that were ingested on merged
pull requests (#716 tax, #717 TANF/CCDF) but never released. The program bundles name 187 documents that only these
scopes hold (by bundle: North Carolina individual income tax 98, South Dakota CCDF 40, the TY2025 state forms, the CCDF
rulebooks and rate schedules).

## Scopes added (24)

From docs/ingest-runs/2026-09-15-tax.md (#716):

- `us/guidance/2026-09-15-irs-guidance-rev-proc`
- `us/regulation/2026-09-15-title-26-part-301-closure-title-26-part-301`
- `2026-09-15-income-tax-forms-ty2025` of us-hi, us-il, us-ks, us-la, us-ma, us-me, us-mn, us-nc, us-ne, us-ny, us-ri
- `us-nc/statute/2026-09-15-income-tax-chapter-r2026-10-11-without-union-sections-consolidated` (below)

From docs/ingest-runs/2026-09-15-tanf-ccdf.md (#717):

- `2026-09-15-ccdf-subsidy-rules` of us-in and us-ky (manual) and us-ne, us-nm, us-sd and us-vt (regulation)
- `2026-09-15-ccdf-rate-schedules` of us-ms, us-ut, us-vt and us-wi (policy)

Every added scope has a coverage file with `complete: true`.

## North Carolina: chapter 105 without the four sections the released union serves

`us-nc/statute/2026-09-15-income-tax-chapter` (205 rows: 102 section roots and 103 text blocks) shares four section
roots with the released `us-nc/statute/2026-08-03-nc-income-tax-current-union`: G.S. 105-153.5, 105-153.7, 105-153.9
and 105-153.11. The union holds them as sections with their text; the chapter scope holds body-less roots with one
`block-1` row each. This is the swap the tax note left open. The successor keeps the released sections and takes the
other 197 rows of the chapter scope (built from this worktree's corpus root, which held the chapter scope as extracted):

```bash
B=$PWD/data/corpus
CH=2026-09-15-income-tax-chapter
ARGS=(); for p in $(jq -r .citation_path $B/provisions/us-nc/statute/$CH.jsonl \
    | grep -vE '^us-nc/statute/105/105-153\.(5|7|9|11)(/|$)'); do
  ARGS+=(--include-citation-from "$CH=$p"); done
uv run --extra dev python scripts/consolidate_release_scopes.py --base $B \
  --jurisdiction us-nc --document-class statute --source-version $CH "${ARGS[@]}" \
  --target-version $CH-r2026-10-11-without-union-sections-consolidated
```

The original chapter scope is not selected.

## Not selected

- The wave-5 runs still on open pull requests: #714 (Medicaid/CHIP: MAGI verification plans, 1115 STCs, the WY
  eligibility manual closure, Medicaid and CHIP income tables), #715 (SNAP/WIC) and #718 (SSI/LIHEAP/Medicare). Their
  manifests and run notes are not on `main`.
- `us-oh/regulation/...-agency-5180-6-chapter-5180-6-1`, `us-or/regulation/...-chapter-414-division-175` and
  `us-ma/statute/...-chapter-62`: already served through the wave-6 successors K7, K8 and K11.
- The three scopes the wave-6 release held out for the owner, though bundles name one document in each:
  `us/rulemaking/2026-06-03-cms-2454-ifc-...` (the CMS-2454 FR scope), `us-mn/guidance/2026-07-22-mn-income-tax-inflation-adjusted-amounts-2026`
  and `us-mo/regulation/2026-10-06-w6-benefits-regulation-mo` (the page-level duplicate of the selected section-level scope).

## Checks

- No citation path in two selected scopes: 402,968 paths over 1,469 scopes, 0 duplicates (402,143 in the wave-6 cut).
- `validate-release --ignore-r2-missing`: ok, 1,469 scopes, 0 errors, 564 warnings: the 562 of the wave-6 cut and 2
  advisory `unsectioned_document_body` warnings in added scopes.
- Citation-path ratchets over every locked provisions file plus the 24 scopes (2,328 files): `block_n` 84,846 → 84,985
  (+139), `page_n` 176,070 → 176,322 (+252), `uppercase_segments` 18,761 → 18,796 (+35); the other families unchanged.

## Activation

The release carries every pair of the active cut, so its takeover displaces only `us-rulespec-2026-10-07-w6-bundle-gaps-union`.
TheAxiomFoundation/axiom-corpus#799 (`us-rulespec-2026-10-09-az-des-ece-dated`) is cut from the same base: whichever of
the two activates second must also carry the other's added scopes, or the monotonicity gate refuses it.

## What the signer runs next

1. With a clean tracked tree, sign and lock the 24 scopes of `docs/ingest-runs/2026-10-11-w5-remainder-unsigned-scopes.tsv`
   (`sign-ingest-manifest --jurisdiction J --document-class C --version V --command "rebuild: see <run_note>" --lock`).
2. `corpus push --changed-since origin/main`, then `corpus verify --remote --changed-since origin/main`.
3. Raise the three ratchets (`scripts/validate_citation_paths.py --update-baselines` over the full tree) and commit the
   selector; `guard-ingested` and `corpus verify --attest`; open the pull request.
4. After the merge, `publish.yml` runs on the new selector; then the activation preview and the protected activation.
