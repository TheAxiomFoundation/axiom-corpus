# Wave 6 brief — State SNAP, WIC, SSI state supplement, LIHEAP and unemployment insurance documents (group `benefits`)

Read `00-common-preamble.md` first. Worktree `/Users/pavelmakarchuk/axiom-corpus-worktrees/w6-benefits`, branch `discovery/ingest-w6-benefits` (cut from main). Input:
`/Users/pavelmakarchuk/axiom-corpus-worktrees/bundle-gaps/docs/coverage/program-bundle-gaps-2026-10-06/wave6/benefits.csv` (265 rows, 220 of them in Tier 1; 37 jurisdictions).

## Rows by action

| action | rows | top hosts |
|---|---:|---|
| EXTRACT-MANIFEST | 37 | dbmefaapolicy.azdes.gov 18, law.lis.virginia.gov 6, fns.usda.gov 3, (no address) 2, apps.azsos.gov 1, cdss.ca.gov 1 |
| FETCH | 133 | nj.gov 10, lawfilesext.leg.wa.gov 10, oklahoma.gov 6, oui.doleta.gov 5, cdss.ca.gov 5, revisor.mo.gov 5 |
| CHECK-PUBLISHER | 9 | oscn.net 5, alabamaretail.org 1, ctdssmap.com 1, rockfordha.org 1, oregon.public.law 1 |
| OFFICIAL-SOURCE | 41 | law.cornell.edu 32, law.justia.com 7, caselaw.findlaw.com 1, casetext.com 1 |
| DEAD-LINK | 23 | le.utah.gov 4, arkansas.gov 2, myflfamilies.com 2, dsd.state.md.us 2, dssmanuals.mo.gov 2, services.dpw.state.pa.us 2 |
| BLOCKED-CHECK | 22 | dbmefaapolicy.azdes.gov 11, mass.gov 4, nysenate.gov 4, ldh.la.gov 2, leginfo.legislature.ca.gov 1 |

## Rows by jurisdiction

us-ak 8, us-al 11, us-ar 3, us-az 31, us-ca 9, us-co 3, us-ct 4, us-dc 2, us-de 3, us-fl 3, us-hi 3, us-ia 1, us-id 2, us-il 19, us-in 5, us-ks 1, us-ky 2, us-la 4, us-ma 12, us-md 8, us-me 8, us-mi 4, us-mo 14, us-nc 3, us-ne 6, us-nj 10, us-ny 16, us-ok 13, us-or 3, us-pa 7, us-sc 7, us-tx 5, us-ut 8, us-va 7, us-vt 2, us-wa 17, us-wi 1

## Run notes to read first

- `docs/ingest-runs/2026-09-10-snap-state-manual-completion-batch-1.md`
- `docs/ingest-runs/2026-09-11-snap-superseding-scopes-batch-1.md`
- `docs/ingest-runs/2026-09-10-ssi-state-supplements-batch-1.md`
- `docs/ingest-runs/2026-09-10-liheap-state-plans-fy2026.md`
- `docs/ingest-runs/2026-09-14-liheap-matrix-ssi-standards.md`
- `docs/ingest-runs/2026-09-10-wic-state-manuals-batch-2.md`
- wave 5 snap-wic and ssi-liheap-medicare notes (branches)

## Notes

- Unemployment insurance has no earlier wave: state UI statutes (benefit formula, weekly benefit amount, maximums) are law, take them from the legislature like other state statutes; benefit-amount tables published by the state workforce agency are guidance.
