# Wave 7 brief — Federal documents (group `federal`)

Read `00-common-preamble.md` first. Worktree `<worktrees>/w7-federal`, branch `discovery/ingest-w7-federal` (cut from main). Input:
`<worktrees>/w7-workorder/docs/coverage/program-bundle-gaps-2026-10-12/wave7/federal.csv` (13 rows, 13 of them in Tier 1; 1 jurisdictions).

## Rows by action

| action | rows | top hosts |
|---|---:|---|
| PATH-ONLY | 10 | (no address) |
| FETCH | 2 | www.irs.gov 2 |
| DEAD-LINK | 1 | www.acf.hhs.gov 1 |

## Rows by jurisdiction

us 13

## Run notes to read first

- `docs/ingest-runs/2026-10-06-w6-federal.md`

## Notes

- `PATH-ONLY` rows are U.S. Code sections and whole titles or chapters that wave 6 skipped (time box). For a title or chapter (`us/statute/26/subtitle-A`, `us/statute/42/chapter-7`), check first whether a served scope holds its sections; then the gap is the container node, not the text.
- IRS revenue procedures: official PDFs on irs.gov; check the edition each PolicyEngine parameter cites.
