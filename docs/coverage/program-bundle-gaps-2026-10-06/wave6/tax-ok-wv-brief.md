# Wave 6 brief — State individual income tax, EITC and CTC documents, Oklahoma to West Virginia (group `tax-ok-wv`)

Read `00-common-preamble.md` first. Worktree `/Users/pavelmakarchuk/axiom-corpus-worktrees/w6-tax-ok-wv`, branch `discovery/ingest-w6-tax-ok-wv` (cut from main). Input:
`/Users/pavelmakarchuk/axiom-corpus-worktrees/bundle-gaps/docs/coverage/program-bundle-gaps-2026-10-06/wave6/tax-ok-wv.csv` (394 rows, 392 of them in Tier 1; 12 jurisdictions).

## Rows by action

| action | rows | top hosts |
|---|---:|---|
| EXTRACT-MANIFEST | 83 | (no address) 81, oregon.gov 1, revenue.wi.gov 1 |
| FETCH | 237 | tax.vermont.gov 40, tax.ri.gov 36, tax.virginia.gov 15, oklahoma.gov 14, legislature.vermont.gov 14, pa.gov 13 |
| CHECK-PUBLISHER | 15 | oregon.public.law 4, oscn.net 2, taxsim.nber.org 2, oklahoma529.com 1, google.com 1, pa529.com 1 |
| OFFICIAL-SOURCE | 16 | law.justia.com 11, taxformfinder.org 2, law.cornell.edu 1, legiscan.com 1, efile.com 1 |
| DEAD-LINK | 36 | le.utah.gov 31, olis.oregonlegislature.gov 2, dor.sc.gov 2, tax.vermont.gov 1 |
| BLOCKED-CHECK | 7 | revenue-pa.custhelp.com 3, governor.ri.gov 1, tax.ri.gov 1, vt529.org 1, vtdigger.org 1 |

## Rows by jurisdiction

us-ok 21, us-or 35, us-pa 21, us-ri 52, us-sc 27, us-tx 1, us-ut 51, us-va 27, us-vt 65, us-wa 19, us-wi 65, us-wv 10

## Run notes to read first

- `docs/ingest-runs/2026-09-14-state-tax-statute-ty2026.md`
- `docs/ingest-runs/2026-09-14-state-tax-regulations.md`
- `docs/ingest-runs/2026-09-10-tax-forms-instructions-guidance-batch-1.md`
- wave 5 tax note (branch discovery/ingest-w5-tax)

## Notes

- Forms and instructions: read the printed tax year; the bundle wants the editions PolicyEngine cites (TY2025 returns, TY2026 withholding/estimates). Model: `scripts/build_state_tax_statute_ty2026_manifests.py` and the wave-5 `--family forms` mode.
- Statutes: wave 4 took whole income-tax chapters for 16 states (`2026-09-14-income-tax-chapter-*`) and wave 5 more; many statute rows are ALREADY-HELD or one section outside a held chapter. Mirror rows (Justia, Cornell) are law already: find the section in the held chapters first, else take it from the legislature.
- Known blocks (do not retry more than once): AR and MS codes (Lexis), NJ administrative code (Lexis), DC OTR, Maryland Comptroller knowledge base, Kentucky Find a Form, Pennsylvania forms search, ilga.gov (see the wave-5 tax note).
