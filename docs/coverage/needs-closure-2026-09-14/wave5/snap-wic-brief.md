# Wave 5 brief — SNAP and WIC (group `snap-wic`)

Read `00-common-preamble.md` first. Worktree `/Users/pavelmakarchuk/axiom-corpus-worktrees/w5-snap-wic`, branch
`discovery/ingest-w5-snap-wic` (at main 9b0641afc). Inputs: `wave5/snap-wic-extractable.csv` (34 rows, 2 federal) and
`wave5/snap-wic-review.csv` (337 rows). Schemas `snap-schema.yaml`, `wic-schema.yaml`; reports `snap.md`, `wic.md`;
the check `check_snap_wic.py` (its `-hits.jsonl` files hold every PRESENT snippet). Queues:
`manifests/snap-completion-agent-queue.yaml`, `manifests/state-snap-manual-agent-queue.yaml`, `manifests/wic-agent-queue.yaml`.

SNAP and WIC are at 1% EXTRACTABLE: **this group is mostly a reading pass**, not a crawl. Keep Part A short.

## Part A targets (34 cells)

1. **Federal (2 elements, 102 cells)**: `snap_g12` — the FNS broad-based categorical eligibility state chart
   (`fns.usda.gov/snap/broad-based-categorical-eligibility`, the note has the URL); one official-documents scope
   `us/guidance/2026-09-15-snap-bbce-state-chart`. `wic_g06` — the WIC Federal Register final rule the element wants
   (read `wic-schema.yaml` for which rule; `extract-federal-register` by document number, version
   `2026-09-15-wic-federal-register-<docnum>`).
2. **SNAP state tables/transmittals (12 cells, FL GA KY MA MI NC ND NH)** and **manual sections (9 cells, GA KY MA MI ND NH
   WY)**: each note lists the scopes already searched and the regex that missed; open those scopes first — several are
   likely pattern misses (ALREADY-HELD). Only where the document is genuinely absent, take it (FY2026 transmittals were
   taken for 22 states under `2026-09-14-snap-fy2026-*`; check there too). North Dakota: the `2026-09-11-nd-snap-manual-supersede`
   scope is on disk but held until 2026-10-01 — do not re-extract it; record `HELD-UNTIL-2026-10-01`.
3. **SNAP state plans (NM, TX, 2 cells)**: no state posts its 7 CFR 272.2 plan (09-13 finding); confirm once, record ABSENT.
4. **WIC manual sections (8 cells, CT KY ME MN OR RI; TN regulation)**: same approach — check the held WIC scope, take only
   what is missing (`2026-09-15-wic-state-manual-closure`).

## Part B — reading pass (337 cells; the main job)

`wic_s31` (50 states) and `wic_s30` (34): read the cited provisions; if the hit is the same boilerplate everywhere, say so
once and record ABSENT-IN-CITED with the carrying family. `snap_s15` (18), `snap_s16` (13), `snap_s32` (13), then the rest.
The `-hits.jsonl` files give the snippet without opening the JSONL. Cap ~250 cells.

## Part C

Run note `docs/ingest-runs/2026-09-15-snap-wic.md`, decisions `docs/ingest-runs/2026-09-15-snap-wic-decisions.csv`,
draft PR.
