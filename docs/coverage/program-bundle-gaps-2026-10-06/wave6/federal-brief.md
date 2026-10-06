# Wave 6 brief — Federal law and guidance of all 13 programs (the federal layer, inherited by all 51 state pages) (group `federal`)

Read `00-common-preamble.md` first. Worktree `/Users/pavelmakarchuk/axiom-corpus-worktrees/w6-federal`, branch `discovery/ingest-w6-federal` (cut from main). Input:
`/Users/pavelmakarchuk/axiom-corpus-worktrees/bundle-gaps/docs/coverage/program-bundle-gaps-2026-10-06/wave6/federal.csv` (333 rows, 325 of them in Tier 1; 1 jurisdiction).

## Rows by action

| action | rows | top hosts |
|---|---:|---|
| EXTRACT-MANIFEST | 8 | (no address) 7, medicaid.gov 1 |
| FETCH | 185 | irs.gov 114, medicaid.gov 30, cms.gov 6, federalregister.gov 4, govinfo.gov 4, macpac.gov 4 |
| CHECK-PUBLISHER | 3 | ccf.georgetown.edu 1, irc.bloombergtax.com 1, medicaidscreener.com 1 |
| OFFICIAL-SOURCE | 19 | law.cornell.edu 19 |
| DEAD-LINK | 4 | medicaid.gov 2, acf.gov 1, fns-prod.azureedge.net 1 |
| BLOCKED-CHECK | 63 | ssa.gov 41, fns.usda.gov 9, congress.gov 6, cbo.gov 3, medicareinteractive.org 2, usda.gov 2 |
| PATH-ONLY | 51 | (no address) 51 |

## Run notes to read first

- `docs/ingest-runs/2026-09-13-federal-statute-layer.md`
- `docs/ingest-runs/2026-09-13-federal-cfr-layer.md`
- `docs/ingest-runs/2026-09-13-federal-guidance-layer.md`
- `docs/ingest-runs/2026-09-10-ssi-poms-si.md`
- `docs/ingest-runs/2026-09-10-medicare-cms-iom-100-01.md`
- wave 5 tax and ssi-liheap-medicare notes (branches)

## Notes

- Each document clears the federal layer of every state page: highest leverage of the wave.
- PATH-ONLY rows are USC/CFR sections the selected scopes lack: confirm under data/corpus/provisions/us/{statute,regulation}/ first (many sit in unreleased wave-3/4/5 closure scopes), then `extract-usc` / `extract-ecfr` for the rest.
- irs.gov: forms, instructions, publications and IRB/irs-drop revenue procedures; follow the wave-5 tax note (`scripts/build_tax_forms_manifests.py --wave5-federal`).
- ssa.gov refused the plain client: POMS and SSA pages have documented routes in the SSI POMS note; else OUTREACH.
- medicaid.gov / cms.gov: guidance letters (SMD/SHO/CIB) and program pages; congress.gov public laws refused the plain client (use govinfo.gov PLAW, the official publisher of enrolled public laws).
