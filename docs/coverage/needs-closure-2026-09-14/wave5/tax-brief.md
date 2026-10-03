# Wave 5 brief — individual income tax (group `tax`)

Read `00-common-preamble.md` first. Worktree `/Users/pavelmakarchuk/axiom-corpus-worktrees/w5-tax`, branch
`discovery/ingest-w5-tax` (at main 9b0641afc). Inputs: `wave5/tax-extractable.csv` (454 rows) and `wave5/tax-review.csv`
(29 rows). Schema `tax-schema.yaml`, report `tax.md` (its "statute coverage in the selection" column is 09-11 text — verify
against the corpus, not the column).

## Part A targets, in order of leverage

1. **Federal, 35 elements (each clears 51 cells).** Groups from the notes:
   - `F116`–`F118` and neighbours: "eCFR title 26 part 1 / part 31 section not selected". Wave 3 (#701) took 26 CFR parts 1
     and 31 into `us/regulation/2026-09-13-title-26-part-1` and `...-part-31` (confirm the version names under
     `data/corpus/provisions/us/regulation/`). Check whether the section paths the elements need
     (`us/regulation/26/1/<section>`) are there. If they are, these are ALREADY-HELD (the 09-11 check predates the scope);
     if a section is genuinely absent (parts 1 and 31 are huge; the eCFR extractor may have subset filters), extract the
     missing sections with `extract-ecfr` under a new version `2026-09-15-title-26-part-1-closure`.
   - `F052`: 26 U.S.C. 71 and 215 (alimony; repealed for post-2018 instruments but still law for older ones): check the
     selected `us/statute` scopes for `us/statute/26/71`; if absent, `extract-usc` title 26 for those sections.
   - `F088`: Rev. Proc. 2025-19 (IRB 2025-23) — irs.gov/irb posts the bulletin PDF; official-documents manifest.
   - `F108`: Publication 15-T (irs.gov/forms-pubs/about-publication-15-t) — official-documents manifest, PDF has a text layer.
   - Any other federal row in the CSV: read its note and treat likewise.
2. **State statute, 286 cells across 43 states.** Wave 4 took whole income-tax chapters for AL, AZ, CA, CT, DE, ID, KY,
   MD, ME, MI, MN, NE, NY, OH, UT, VA (`2026-09-14-income-tax-chapter-*`, and the `-r2` versions for AL/DE/NE). For every
   other state in the CSV, first check what statute scopes are selected (the 09-14 selector) and what sections the element
   needs (`tax-schema.yaml` `facts`/`sources`); then take the whole individual-income-tax chapter through
   `extract-state-statutes` where an adapter exists for the state (`manifests/state-income-tax-chapters-2026-09-14.yaml`
   is the template; add rows under a new manifest `manifests/state-income-tax-chapters-2026-09-15.yaml`, version prefix
   `2026-09-15-income-tax-chapter`), or one section per document via
   `scripts/build_state_tax_statute_ty2026_manifests.py --family statute` where the legislature posts sections only.
   Known blocks (do not retry more than once): AR and MS (Lexis-only), DC OTR (403), NJ (Lexis). Record them OUTREACH.
3. **Forms, instructions and rate schedules, 125 cells across 33 states** (`tax-schema.yaml` element ids of family
   `state form instructions and rate schedules`): TY2025 resident return instructions, tax tables/rate schedules and
   the TY2026 withholding/estimated-payment notices from each revenue department. The wave-4 note
   (`2026-09-14-state-tax-statute-ty2026.md`, "Family 2") documents the department indexes and which ones need the Chrome
   fallback (CO, OH) or are blocked (DC OTR, MD Comptroller). Use `scripts/build_state_tax_statute_ty2026_manifests.py
   --family amounts` as the model (extend it with a `--family forms` mode rather than hand-writing manifests). Version
   `2026-09-15-income-tax-forms-ty2025`.
4. **State regulation, 8 cells (AR, DC, DE, MD, NJ, OH, OR, UT):** wave 4 took income-tax regulations for 37 states
   (`2026-09-14-income-tax-regulations`); these eight were not taken — the notes say why. Re-probe once each; take what
   answers.

## Part B

`tax-review.csv` has 29 cells, all element `F06` (TY2026 indexed amounts): read all 29 cited provisions (the 2026-09-14
`ty2026` guidance scopes) and decide.

## Part C

Run note `docs/ingest-runs/2026-09-15-tax.md`, decisions `docs/ingest-runs/2026-09-15-tax-decisions.csv`, draft PR.
