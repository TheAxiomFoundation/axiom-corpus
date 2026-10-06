# Wave 6 brief — State TANF and CCDF documents, Alaska to Nebraska (group `tanf-ccdf-ak-ne`)

Read `00-common-preamble.md` first. Worktree `/Users/pavelmakarchuk/axiom-corpus-worktrees/w6-tanf-ccdf-ak-ne`, branch `discovery/ingest-w6-tanf-ccdf-ak-ne` (cut from main). Input:
`/Users/pavelmakarchuk/axiom-corpus-worktrees/bundle-gaps/docs/coverage/program-bundle-gaps-2026-10-06/wave6/tanf-ccdf-ak-ne.csv` (372 rows, 371 of them in Tier 1; 30 jurisdictions).

## Rows by action

| action | rows | top hosts |
|---|---:|---|
| EXTRACT-MANIFEST | 3 | (no address) 2, ncleg.gov 1 |
| FETCH | 235 | cdss.ca.gov 23, in.gov 13, dhhs.ne.gov 12, revisor.mn.gov 11, nebraskalegislature.gov 8, my.dpss.lacounty.gov 7 |
| CHECK-PUBLISHER | 22 | ctcare4kids.com 5, louisianabelieves.com 5, earlychildhood.marylandpublicschools.org 3, stgenssa.sccgov.org 2, ctoec.org 2, help.workworldapp.com 1 |
| OFFICIAL-SOURCE | 62 | law.cornell.edu 58, regulations.justia.com 3, law.justia.com 1 |
| DEAD-LINK | 15 | cga.ct.gov 5, doa.la.gov 2, epolicy.dpss.lacounty.gov 1, cde.ca.gov 1, hawaii.edu 1, ilga.gov 1 |
| BLOCKED-CHECK | 33 | leginfo.legislature.ca.gov 14, mass.gov 8, des.az.gov 3, michigan.gov 3, dese.mo.gov 2, dbmefaapolicy.azdes.gov 1 |
| PATH-ONLY | 2 | (no address) 2 |

## Rows by jurisdiction

us-ak 5, us-al 4, us-ar 3, us-az 7, us-ca 52, us-co 1, us-ct 16, us-dc 8, us-de 8, us-fl 3, us-ga 6, us-hi 7, us-ia 8, us-id 4, us-il 20, us-in 16, us-ks 13, us-ky 10, us-la 17, us-ma 12, us-md 19, us-me 11, us-mi 6, us-mn 19, us-mo 16, us-ms 11, us-mt 22, us-nc 11, us-nd 15, us-ne 22

## Run notes to read first

- `docs/ingest-runs/2026-09-14-tanf-whole-manuals-md-comar.md`
- `docs/ingest-runs/2026-09-10-tanf-state-policy-manuals-batch-1.md`
- `docs/ingest-runs/2026-09-10-ccdf-state-plans-fy2025-2027.md`
- `docs/ingest-runs/2026-09-13-acf-state-plans.md`
- wave 5 tanf-ccdf note (branch discovery/ingest-w5-tanf-ccdf)

## Notes

- Agency manuals: take whole manuals or chapters where the publisher posts them (wave 4 note), else one document per cited section/page.
- CCDF: state plans (ACF), subsidy rulebooks, payment-rate schedules and sliding-fee scales; the wave-5 tanf-ccdf note lists the publishers already probed.
- Many state agency sites refuse plain clients (mass.gov, michigan.gov, dhs.ri.gov): check the blocked-publishers note before recording OUTREACH.
