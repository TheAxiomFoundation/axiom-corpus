# Wave 5 brief — TANF and CCDF (group `tanf-ccdf`)

Read `00-common-preamble.md` first. Worktree `/Users/pavelmakarchuk/axiom-corpus-worktrees/w5-tanf-ccdf`, branch
`discovery/ingest-w5-tanf-ccdf` (at main 9b0641afc). Inputs: `wave5/tanf-ccdf-extractable.csv` (75 rows, 8 federal) and
`wave5/tanf-ccdf-review.csv` (418 rows). Schemas `tanf-schema.yaml`, `ccdf-schema.yaml`; reports `tanf.md`, `ccdf.md`;
builder `build_tanf_ccdf_matrix.py` (its `CCDF_RULEBOOK_LISTED` / `CCDF_RATE_SHEETS` dicts carry the publisher URLs the
09-11 inventory found). Queues: `manifests/tanf-agent-queue.yaml`, `manifests/ccdf-agent-queue.yaml`.

## Part A targets (75 cells)

1. **Federal, 8 elements (each clears 51 cells).** `ccdf-f-usc-1` … `-6`: the CCDBG Act, 42 U.S.C. 9857–9858q (secs.
   658A–658S) — not in any `us/statute` scope. `extract-usc` title 42 chapter 105 subchapter II-B, version
   `2026-09-15-ccdbg-statute-title-42` (`inventory-usc` then `extract-usc`, as the wave-3 federal statute layer did;
   read `docs/ingest-runs/2026-09-13-*federal-statute*.md` for the USLM en-dash gotchas). `tanf-f-usc-614` (42 U.S.C.
   614): check the selected TANF statute scope first (`us/statute/2026-09-13-tanf-statute-*`); if it stops before 614,
   take it in the same run. The eighth row: read its note.
2. **Arizona TANF (13 cells, `tanf-s02` … `-s19`)**: AZ DES is a durable Cloudflare block (09-14 outreach list). Probe
   once with the plain client; if blocked, record OUTREACH for all 13 and move on. Do not work around it.
3. **CCDF state subsidy rulebooks (`ccdf-s29`, 15 states: ID IN KY ME NE NM OH OK OR RI SC SD TN VT + 1)**: the notes name the
   codified rule chapter on each state's administrative-code publisher (e.g. IDAPA 16.06.12 on the OARC index). Where the
   state's administrative code already has an adapter or a prior official-documents manifest (grep `manifests/` for the
   publisher host), extend it; version `2026-09-15-ccdf-subsidy-rules`.
4. **CCDF rate and copay schedules (`ccdf-s30`, 13 states: CO CT KY LA MN MS NJ OR PA RI UT VA VT)**: the current
   market-rate / copay sheet the Lead Agency posts (the notes cite the run-note inventory). Wave 4 took 5 states under
   `2026-09-13-ccdf-rate-schedules`; use the same generator (`scripts/build_ccdf_state_plan_manifests.py` has the rate
   family) with version `2026-09-15-ccdf-rate-schedules`.
5. **Indiana plan sections (3 cells)**: read the note; IN's plan was partially taken.

## Part B — reading pass (418 cells)

Top elements: `tanf-s18` child-care exception to sanctions (40 states), `ccdf-s28` amendments (29), `ccdf-s30` (29,
where the plan carries values "as of submission"), `tanf-s02` (27), `ccdf-s29` (24). Sample 6 states per element as the
preamble says. For `ccdf-s28`/`ccdf-s30` REVIEW cells the question is whether the plan text itself is acceptable
evidence for the element (record your reading; the rules repo decides). Cap ~250 cells.

## Part C

Run note `docs/ingest-runs/2026-09-15-tanf-ccdf.md`, decisions `docs/ingest-runs/2026-09-15-tanf-ccdf-decisions.csv`,
draft PR.
