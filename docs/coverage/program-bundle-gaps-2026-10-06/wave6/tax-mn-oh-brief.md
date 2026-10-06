# Wave 6 brief — State individual income tax, EITC and CTC documents, Minnesota to Ohio (group `tax-mn-oh`)

Read `00-common-preamble.md` first. Worktree `/Users/pavelmakarchuk/axiom-corpus-worktrees/w6-tax-mn-oh`, branch `discovery/ingest-w6-tax-mn-oh` (cut from main). Input:
`/Users/pavelmakarchuk/axiom-corpus-worktrees/bundle-gaps/docs/coverage/program-bundle-gaps-2026-10-06/wave6/tax-mn-oh.csv` (379 rows, 379 of them in Tier 1; 12 jurisdictions).

## Rows by action

| action | rows | top hosts |
|---|---:|---|
| EXTRACT-MANIFEST | 39 | (no address) 39 |
| FETCH | 259 | revenue.state.mn.us 59, tax.ny.gov 29, revisor.mo.gov 24, ncdor.gov 20, dor.mo.gov 18, revenue.nebraska.gov 14 |
| CHECK-PUBLISHER | 24 | klvg4oyd4j.execute-api.us-west-2.amazonaws.com 11, taxsim.nber.org 7, nmonesource.com 4, zillionforms.com 1, newyork.public.law 1 |
| OFFICIAL-SOURCE | 28 | law.justia.com 15, law.cornell.edu 7, taxformfinder.org 2, legiscan.com 2, regulations.justia.com 2 |
| DEAD-LINK | 14 | mtrevenue.gov 4, tax.ny.gov 3, leg.mt.gov 2, tax.ohio.gov 2, billstatus.ls.state.ms.us 1, nj.gov 1 |
| BLOCKED-CHECK | 10 | revenue.nh.gov 10 |
| VENDOR | 5 | advance.lexis.com 5 |

## Rows by jurisdiction

us-mn 64, us-mo 55, us-ms 23, us-mt 55, us-nc 22, us-nd 16, us-ne 24, us-nh 11, us-nj 27, us-nm 26, us-ny 39, us-oh 17

## Run notes to read first

- `docs/ingest-runs/2026-09-14-state-tax-statute-ty2026.md`
- `docs/ingest-runs/2026-09-14-state-tax-regulations.md`
- `docs/ingest-runs/2026-09-10-tax-forms-instructions-guidance-batch-3-retry.md`
- wave 5 tax note (branch discovery/ingest-w5-tax)

## Notes

- Forms and instructions: read the printed tax year; the bundle wants the editions PolicyEngine cites (TY2025 returns, TY2026 withholding/estimates). Model: `scripts/build_state_tax_statute_ty2026_manifests.py` and the wave-5 `--family forms` mode.
- Statutes: wave 4 took whole income-tax chapters for 16 states (`2026-09-14-income-tax-chapter-*`) and wave 5 more; many statute rows are ALREADY-HELD or one section outside a held chapter. Mirror rows (Justia, Cornell) are law already: find the section in the held chapters first, else take it from the legislature.
- Known blocks (do not retry more than once): AR and MS codes (Lexis), NJ administrative code (Lexis), DC OTR, Maryland Comptroller knowledge base, Kentucky Find a Form, Pennsylvania forms search, ilga.gov (see the wave-5 tax note).
