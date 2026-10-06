# Wave 6 brief — State individual income tax, EITC and CTC documents, Alabama to Hawaii (group `tax-al-hi`)

Read `00-common-preamble.md` first. Worktree `/Users/pavelmakarchuk/axiom-corpus-worktrees/w6-tax-al-hi`, branch `discovery/ingest-w6-tax-al-hi` (cut from main). Input:
`/Users/pavelmakarchuk/axiom-corpus-worktrees/bundle-gaps/docs/coverage/program-bundle-gaps-2026-10-06/wave6/tax-al-hi.csv` (399 rows, 393 of them in Tier 1; 10 jurisdictions).

## Rows by action

| action | rows | top hosts |
|---|---:|---|
| EXTRACT-MANIFEST | 89 | (no address) 83, azdor.gov 2, ftb.ca.gov 1, sos.state.co.us 1, portal.ct.gov 1, eregulations.ct.gov 1 |
| FETCH | 201 | dfa.arkansas.gov 60, files.hawaii.gov 16, arkleg.state.ar.us 15, azleg.gov 15, revenue.alabama.gov 14, azdor.gov 12 |
| CHECK-PUBLISHER | 5 | taxsim.nber.org 2, collegecounts529.com 1, olls.info 1, zillionforms.com 1 |
| OFFICIAL-SOURCE | 25 | law.justia.com 19, codes.findlaw.com 2, regulations.justia.com 2, taxformfinder.org 1, legiscan.com 1 |
| DEAD-LINK | 6 | cga.ct.gov 4, dfa.arkansas.gov 1, dochub.com 1 |
| BLOCKED-CHECK | 54 | tax.colorado.gov 21, leginfo.legislature.ca.gov 15, ftb.ca.gov 11, capitol.hawaii.gov 7 |
| VENDOR | 18 | advance.lexis.com 17, codelibrary.amlegal.com 1 |
| PATH-ONLY | 1 | (no address) 1 |

## Rows by jurisdiction

us-al 22, us-ar 90, us-az 52, us-ca 71, us-co 46, us-ct 24, us-dc 10, us-de 13, us-ga 29, us-hi 42

## Run notes to read first

- `docs/ingest-runs/2026-09-14-state-tax-statute-ty2026.md`
- `docs/ingest-runs/2026-09-14-state-tax-regulations.md`
- `docs/ingest-runs/2026-09-10-tax-forms-instructions-guidance-batch-1.md`
- wave 5 tax note (branch discovery/ingest-w5-tax)

## Notes

- Forms and instructions: read the printed tax year; the bundle wants the editions PolicyEngine cites (TY2025 returns, TY2026 withholding/estimates). Model: `scripts/build_state_tax_statute_ty2026_manifests.py` and the wave-5 `--family forms` mode.
- Statutes: wave 4 took whole income-tax chapters for 16 states (`2026-09-14-income-tax-chapter-*`) and wave 5 more; many statute rows are ALREADY-HELD or one section outside a held chapter. Mirror rows (Justia, Cornell) are law already: find the section in the held chapters first, else take it from the legislature.
- Known blocks (do not retry more than once): AR and MS codes (Lexis), NJ administrative code (Lexis), DC OTR, Maryland Comptroller knowledge base, Kentucky Find a Form, Pennsylvania forms search, ilga.gov (see the wave-5 tax note).
