# Wave 6 brief — State TANF and CCDF documents, New Hampshire to Wyoming (group `tanf-ccdf-nh-wy`)

Read `00-common-preamble.md` first. Worktree `/Users/pavelmakarchuk/axiom-corpus-worktrees/w6-tanf-ccdf-nh-wy`, branch `discovery/ingest-w6-tanf-ccdf-nh-wy` (cut from main). Input:
`/Users/pavelmakarchuk/axiom-corpus-worktrees/bundle-gaps/docs/coverage/program-bundle-gaps-2026-10-06/wave6/tanf-ccdf-nh-wy.csv` (341 rows, 340 of them in Tier 1; 21 jurisdictions).

## Rows by action

| action | rows | top hosts |
|---|---:|---|
| EXTRACT-MANIFEST | 1 | nj.gov 1 |
| FETCH | 191 | app.leg.wa.gov 31, docs.legis.wisconsin.gov 20, secure.sos.state.or.us 15, codes.ohio.gov 13, dss.nv.gov 10, legislature.vermont.gov 7 |
| CHECK-PUBLISHER | 31 | oregon.public.law 9, nmececd.org 5, drive.google.com 5, texas-sos.appianportalsgov.com 3, scchildcare.org 2, bccap.org 1 |
| OFFICIAL-SOURCE | 72 | law.cornell.edu 69, law.justia.com 2, regulations.justia.com 1 |
| DEAD-LINK | 25 | otda.ny.gov 7, ocfs.ny.gov 6, emanuals.jfs.ohio.gov 2, twc.texas.gov 2, oklahoma.gov 1, oregon.gov 1 |
| BLOCKED-CHECK | 15 | dhs.ri.gov 8, dhhs.nh.gov 2, nysenate.gov 2, childcare.virginia.gov 2, childcarenj.gov 1 |
| VENDOR | 6 | okrules.elaws.us 6 |

## Rows by jurisdiction

us-nh 9, us-nj 15, us-nm 14, us-nv 12, us-ny 20, us-oh 17, us-ok 23, us-or 28, us-pa 7, us-ri 13, us-sc 5, us-sd 11, us-tn 3, us-tx 37, us-ut 14, us-va 15, us-vt 20, us-wa 44, us-wi 22, us-wv 6, us-wy 6

## Run notes to read first

- `docs/ingest-runs/2026-09-14-tanf-whole-manuals-md-comar.md`
- `docs/ingest-runs/2026-09-10-tanf-state-policy-manuals-batch-2.md`
- `docs/ingest-runs/2026-09-10-ccdf-state-plans-fy2025-2027.md`
- `docs/ingest-runs/2026-09-13-acf-state-plans.md`
- wave 5 tanf-ccdf note (branch discovery/ingest-w5-tanf-ccdf)

## Notes

- Agency manuals: take whole manuals or chapters where the publisher posts them (wave 4 note), else one document per cited section/page.
- CCDF: state plans (ACF), subsidy rulebooks, payment-rate schedules and sliding-fee scales; the wave-5 tanf-ccdf note lists the publishers already probed.
- Many state agency sites refuse plain clients (mass.gov, michigan.gov, dhs.ri.gov): check the blocked-publishers note before recording OUTREACH.
