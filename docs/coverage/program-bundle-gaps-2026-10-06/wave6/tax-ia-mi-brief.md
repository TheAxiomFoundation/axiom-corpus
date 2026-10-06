# Wave 6 brief — State individual income tax, EITC and CTC documents, Iowa to Michigan (group `tax-ia-mi`)

Read `00-common-preamble.md` first. Worktree `/Users/pavelmakarchuk/axiom-corpus-worktrees/w6-tax-ia-mi`, branch `discovery/ingest-w6-tax-ia-mi` (cut from main). Input:
`/Users/pavelmakarchuk/axiom-corpus-worktrees/bundle-gaps/docs/coverage/program-bundle-gaps-2026-10-06/wave6/tax-ia-mi.csv` (404 rows, 401 of them in Tier 1; 11 jurisdictions).

## Rows by action

| action | rows | top hosts |
|---|---:|---|
| EXTRACT-MANIFEST | 40 | (no address) 37, ilga.gov 1, mass.gov 1, marylandcomptroller.gov 1 |
| FETCH | 238 | maine.gov 52, revenue.ky.gov 30, revenue.iowa.gov 21, legislature.idaho.gov 17, taxarchive.illinois.gov 13, dam.ldr.la.gov 13 |
| CHECK-PUBLISHER | 21 | mainelegislature.org 11, taxsim.nber.org 3, content.govdelivery.com 1, isave529.com 1, idsaves.org 1, brightstart.com 1 |
| OFFICIAL-SOURCE | 13 | law.justia.com 10, law.cornell.edu 1, codes.findlaw.com 1, taxformfinder.org 1 |
| DEAD-LINK | 26 | malegislature.gov 10, ilga.gov 9, marylandtaxes.gov 4, revenue.ky.gov 2, witnessslips.ilga.gov 1 |
| BLOCKED-CHECK | 64 | mass.gov 33, michigan.gov 30, revenue.iowa.gov 1 |
| VENDOR | 2 | govt.westlaw.com 2 |

## Rows by jurisdiction

us-ia 35, us-id 41, us-il 37, us-in 15, us-ks 21, us-ky 37, us-la 28, us-ma 45, us-md 25, us-me 75, us-mi 45

## Run notes to read first

- `docs/ingest-runs/2026-09-14-state-tax-statute-ty2026.md`
- `docs/ingest-runs/2026-09-14-state-tax-regulations.md`
- `docs/ingest-runs/2026-09-10-tax-forms-instructions-guidance-batch-2.md`
- wave 5 tax note (branch discovery/ingest-w5-tax)

## Notes

- Forms and instructions: read the printed tax year; the bundle wants the editions PolicyEngine cites (TY2025 returns, TY2026 withholding/estimates). Model: `scripts/build_state_tax_statute_ty2026_manifests.py` and the wave-5 `--family forms` mode.
- Statutes: wave 4 took whole income-tax chapters for 16 states (`2026-09-14-income-tax-chapter-*`) and wave 5 more; many statute rows are ALREADY-HELD or one section outside a held chapter. Mirror rows (Justia, Cornell) are law already: find the section in the held chapters first, else take it from the legislature.
- Known blocks (do not retry more than once): AR and MS codes (Lexis), NJ administrative code (Lexis), DC OTR, Maryland Comptroller knowledge base, Kentucky Find a Form, Pennsylvania forms search, ilga.gov (see the wave-5 tax note).
