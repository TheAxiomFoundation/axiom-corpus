# Wave 6 brief — State Medicaid, CHIP and Medicare documents (group `health`)

Read `00-common-preamble.md` first. Worktree `/Users/pavelmakarchuk/axiom-corpus-worktrees/w6-health`, branch `discovery/ingest-w6-health` (cut from main). Input:
`/Users/pavelmakarchuk/axiom-corpus-worktrees/bundle-gaps/docs/coverage/program-bundle-gaps-2026-10-06/wave6/health.csv` (128 rows, 127 of them in Tier 1; 30 jurisdictions).

## Rows by action

| action | rows | top hosts |
|---|---:|---|
| EXTRACT-MANIFEST | 2 | (no address) 1, regulations.delaware.gov 1 |
| FETCH | 77 | dhcs.ca.gov 11, hfs.illinois.gov 9, medicaid.ms.gov 8, app.leg.wa.gov 7, portal.ct.gov 5, in.gov 3 |
| CHECK-PUBLISHER | 13 | mmcor.phpcoalition.org 2, california.public.law 1, stgenssa.sccgov.org 1, coloradoimmigrant.org 1, connectforhealthco.com 1, healthfirstcolorado.com 1 |
| OFFICIAL-SOURCE | 15 | law.cornell.edu 14, law.justia.com 1 |
| DEAD-LINK | 5 | ilga.gov 3, dss.mo.gov 1, sharedsystems.dhsoha.state.or.us 1 |
| BLOCKED-CHECK | 16 | leginfo.legislature.ca.gov 6, michigan.gov 4, hcpf.colorado.gov 3, klrd.gov 1, ldh.la.gov 1, info.nystateofhealth.ny.gov 1 |

## Rows by jurisdiction

us-al 3, us-ar 1, us-ca 21, us-co 8, us-ct 5, us-dc 1, us-de 3, us-fl 2, us-ga 5, us-ia 3, us-il 19, us-in 4, us-ks 2, us-la 2, us-ma 2, us-me 1, us-mi 5, us-mo 4, us-ms 8, us-nd 1, us-nv 1, us-ny 3, us-or 7, us-sc 1, us-tn 1, us-tx 1, us-va 1, us-wa 10, us-wi 2, us-wy 1

## Run notes to read first

- `docs/ingest-runs/2026-09-10-medicaid-state-eligibility-manuals-batch-1.md`
- `docs/ingest-runs/2026-09-10-chip-state-eligibility-manuals.md`
- `docs/ingest-runs/2026-09-13-cms-state-plans.md`
- `docs/ingest-runs/2026-09-14-msp-charts-snap-fy2026.md`
- wave 5 medicaid-chip note (branch discovery/ingest-w5-medicaid-chip)

## Notes

- Medicaid/CHIP eligibility manuals, income standards charts, state plan amendments (CMS hosts approved SPAs: official), 1115 waiver terms.
- Medicare state rows are mostly Medicare Savings Program and buy-in materials from state agencies.
