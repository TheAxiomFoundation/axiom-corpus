# Wave 7 brief — State benefit-program documents (SNAP, TANF, CCDF, Medicaid, CHIP, SSI, LIHEAP, WIC, UI) (group `state-benefits`)

Read `00-common-preamble.md` first. Worktree `<axiom-corpus worktrees>/w7-state-benefits`, branch `discovery/ingest-w7-state-benefits` (cut from main). Input:
`<axiom-corpus worktrees>/w7-workorder/docs/coverage/program-bundle-gaps-2026-10-12/wave7/state-benefits.csv` (79 rows, 75 of them in Tier 1; 23 jurisdictions).

## Rows by action

| action | rows | top hosts |
|---|---:|---|
| FETCH | 61 | www.dhs.state.il.us 16, www.dhs.state.mn.us 16, www.sos.state.co.us 4, www.coloradosos.gov 2, apps.legislature.ky.gov 2, dssmanuals.mo.gov 2 |
| CHECK-PUBLISHER | 8 | www.flrules.org 4, earlychildhood.marylandpublicschools.org 1, risos-apa-production-public.s3.amazonaws.com 1, www.scchildcare.org 1, drive.google.com 1 |
| DEAD-LINK | 5 | www.pacodeandbulletin.gov 4, earlychildhood.marylandpublicschools.org 1 |
| MEASURE-CHECK | 4 | www.fns.usda.gov 3, www.azleg.gov 1 |
| OFFICIAL-SOURCE | 1 | www.law.cornell.edu 1 |

## Rows by jurisdiction

us-ar 1, us-az 1, us-ca 1, us-co 10, us-dc 1, us-fl 5, us-hi 1, us-il 17, us-in 1, us-ky 2, us-la 1, us-md 2, us-mi 1, us-mn 16, us-mo 3, us-nc 1, us-nj 2, us-nv 1, us-pa 6, us-ri 1, us-sc 1, us-wa 2, us-wy 2

## Run notes to read first

- `docs/ingest-runs/2026-10-06-w6-benefits.md`
- `docs/ingest-runs/2026-10-06-w6-health.md`
- `docs/ingest-runs/2026-10-06-w6-tanf-ccdf-ak-ne.md`
- `docs/ingest-runs/2026-10-06-w6-tanf-ccdf-nh-wy.md`

## Notes

- Many addresses are query-routed pages: Illinois `page.aspx?item=` (the Cash, SNAP and Medical manual and policy memos), Minnesota `idcplg?...dDocName=` (the Combined Manual and the Employment Services Manual), Pennsylvania `pacodeandbulletin.gov/Display/pacode?file=`, Florida `flrules.org/gateway/RuleNo.asp?ID=`, Colorado `GenerateRulePdf.do?ruleVersionId=` without a file name. Search the local corpus for the publisher's existing scopes first: a held section joins with ALREADY-HELD and its path.
- `MEASURE-CHECK` rows: a wave-6 decision says the corpus holds them, yet the bundle counts them missing.
- Pennsylvania Code pages (`pacodeandbulletin.gov/Display/pacode?file=`) timed out or answered 503 on one plain GET; that is not a dead link. Use the Pennsylvania Code adapter (`src/axiom_corpus/corpus/pennsylvania_code.py`) and check the existing `us-pa/regulation` scopes first.
