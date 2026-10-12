# Program-bundle gaps, 2026-10-12

What the program bundles still lack after wave 6 and the wave-5 remainder, and the wave-7 work orders.

## How the list was made

- Bundles: `manifests/program-bundles/<program>.yaml` on main at b67aa4ba6 (axiom-corpus#825: joins by the full
  address, plan rows honour `not_sources`, fiscal-year ranges are current through their last year; the wave-5
  Medicaid/CHIP, SNAP/WIC and SSI/LIHEAP/Medicare manifests of #714, #715 and #718).
- Measure: the production run of the axiom.org bundle collector at 2026-10-12 17:20 UTC, against the served corpus
  (`us-rulespec-2026-10-07-w6-bundle-gaps-union`). 766 distinct in-scope documents are not in it.
- Each document is checked against the local corpus (every scope, plus the North Carolina successor scope of the
  wave-5 remainder release), the release waiting for activation, and every wave-5/6 decisions file (by `id`,
  `citation_path` and `official_url`): `missing.json`, one record per document with its `status`.
- `triage.json`: one plain GET per open address with the corpus user agent on 2026-10-12 (no retries).

## Where the 766 documents stand

| status | documents | next step |
|---|---:|---|
| PENDING-ACTIVATION | 184 | served once `us-rulespec-2026-10-11-w5-remainder-union` is activated (Max) |
| UNRELEASED-SCOPE | 203 | a scope on main holds them; no release serves it yet (`release-scopes.tsv`, 71 scopes): the next union release |
| DECIDED-ABSENT / DECIDED-ALREADY-HELD / DECIDED-OUTREACH / DECIDED-PRESENT / DECIDED-SKIPPED | 245 | decided in waves 5–6 (OUTREACH and ABSENT stay missing; SKIPPED, ALREADY-HELD and PRESENT rows are in wave 7) |
| WAVE7 | 134 | no decision yet: wave 7 |

## Wave 7

`wave7/00-common-preamble.md` (rules for every agent), one brief and one CSV per group:

| group | documents | Tier 1 | jurisdictions |
|---|---:|---:|---:|
| federal | 13 | 13 | 1 |
| state-benefits | 79 | 75 | 23 |
| state-tax | 16 | 16 | 6 |

Group `rejoin` (44 documents, `wave7/rejoin.csv`) needs no agent: each address names a served document under
another address (a Colorado rule by its file name, a Maryland or Michigan code section, a Kansas KEESM page of another
edition, a Colorado statute cited from Justia), and exactly one served path of the address's document class carries
its identifier. `docs/ingest-runs/2026-10-12-w7-rejoin-decisions.csv` records them as ALREADY-HELD; folded into
`manifests/program-bundles/joins.yaml` with `scripts/apply_wave_decisions.py`.

Each agent writes `docs/ingest-runs/2026-10-12-w7-<group>-decisions.csv`, one row per CSV row; fold them in the same
way.
