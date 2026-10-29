# Wave 7 brief — State income tax, EITC and CTC documents (group `state-tax`)

Read `00-common-preamble.md` first. Worktree `<axiom-corpus worktrees>/w7-state-tax`, branch `discovery/ingest-w7-state-tax` (cut from main). Input:
`<axiom-corpus worktrees>/w7-workorder/docs/coverage/program-bundle-gaps-2026-10-12/wave7/state-tax.csv` (16 rows, 16 of them in Tier 1; 6 jurisdictions).

## Rows by action

| action | rows | top hosts |
|---|---:|---|
| FETCH | 12 | forms.in.gov 5, apps.legislature.ky.gov 3, otr.cfo.dc.gov 2, www.maine.gov 2 |
| MEASURE-CHECK | 2 | (no address) |
| DEAD-LINK | 1 | www.pacodeandbulletin.gov 1 |
| OFFICIAL-SOURCE | 1 | legiscan.com 1 |

## Rows by jurisdiction

us-dc 4, us-in 5, us-ky 3, us-me 2, us-pa 1, us-va 1

## Run notes to read first

- `docs/ingest-runs/2026-10-06-w6-tax-al-hi.md`
- `docs/ingest-runs/2026-10-06-w6-tax-ia-mi.md`
- `docs/ingest-runs/2026-10-06-w6-tax-mn-oh.md`
- `docs/ingest-runs/2026-10-06-w6-tax-ok-wv.md`

## Notes

- Indiana `forms.in.gov/Download.aspx?id=` and Kentucky `statute.aspx?id=` are query-routed: one document per id. Read the document to find its form number or section, then check the local corpus.
- D.C. rows `us-dc/statute/47/47-1806.15` and `.17` (MEASURE-CHECK) were held on axiom-corpus#753; check that PR's state before anything else.
- Pennsylvania Code pages (`pacodeandbulletin.gov/Display/pacode?file=`) timed out or answered 503 on one plain GET; that is not a dead link. Use the Pennsylvania Code adapter (`src/axiom_corpus/corpus/pennsylvania_code.py`) and check the existing `us-pa/regulation` scopes first.
