# Wave 5 brief — Medicaid and CHIP (group `medicaid-chip`)

Read `00-common-preamble.md` first. Worktree `/Users/pavelmakarchuk/axiom-corpus-worktrees/w5-medicaid-chip`, branch
`discovery/ingest-w5-medicaid-chip` (at main 9b0641afc). Inputs: `wave5/medicaid-chip-extractable.csv` (181 rows, all
state-level) and `wave5/medicaid-chip-review.csv` (2,731 rows). Schemas `medicaid-schema.yaml`, `chip-schema.yaml`;
reports `medicaid.md`, `chip.md` (pass-2 method); the builder `tools/build_matrix.py` and its `tools/search-universe.json`
list which scopes were searched per state. Queues: `manifests/medicaid-agent-queue.yaml`, `manifests/chip-agent-queue.yaml`.

Medicaid is now 61% PRESENT / 2% EXTRACTABLE / 29% REVIEW, CHIP 73% / 0% / 26%. The REVIEW column is where the value is.

## Part A targets (181 cells)

1. **Wyoming (M-ST-* rows, "no medicaid document taken for this state")**: the queue records the Wyoming Medicaid manual
   pages (`manual_policy_page_html`, 107 listed, 0 taken) and an eligibility table family (17 listed). Wyoming's tables
   were image-only in earlier passes (see the outreach list in the 09-14 handoff); the manual pages may still be text.
   Probe the index once, take what is text, record the rest OUTREACH/ABSENT with the reason.
2. **Verification and renewal procedures (M-435-918 33 states, M-435-904 31, M-435-908 17, M-435-949/952/912/920/948)**:
   42 CFR 435.9xx elements whose state counterpart is the verification plan / renewal chapter of the eligibility manual.
   Each note names the untaken family on the state's publisher index (e.g. `manual_topic_html (267 of 394 not taken)`,
   with the index URL). Extend the existing medicaid manual generator (`scripts/build_*medicaid*` — find the one that
   produced `2026-09-10-medicaid-state-eligibility-manual`) to take the missing topics/chapters for these states under
   version `2026-09-15-medicaid-eligibility-manual-closure`, or the MAGI verification plan where the state posts one
   separately (medicaid.gov hosts approved MAGI verification plans: `https://www.medicaid.gov/medicaid/eligibility/...`
   — confirm the live index before relying on it).
3. **1115 demonstration STCs (M-ST-1315, 13 states: AK ID KY MT ND NE NV PA SC SD VA WI WY)**: medicaid.gov posts the
   current special terms and conditions PDF per demonstration (`medicaid.gov/medicaid/section-1115-demonstrations/...`).
   One official-documents manifest, version `2026-09-15-medicaid-1115-stc`, one scope per state (`us-xx/policy`). Text
   layers are present on CMS PDFs.
4. **Income and premium tables (M-SS-INCOME-TABLE 6 states; C-SS-INCOME-PREMIUM-TABLE 11: AK AZ FL HI ME MN NH NM OH RI SC)**:
   the annual income-level / premium chart the state posts (manual appendix or a standalone PDF). Version
   `2026-09-15-medicaid-income-table-2026` / `2026-09-15-chip-income-premium-table-2026`.

## Part B — reading pass (2,731 REVIEW cells; this is the main job)

The top REVIEW elements are the 42 CFR 435 FS-level elements with 51 states each (M-435-218, -220, -222, -223, -227 …):
the pass-2 builder found a low-confidence keyword hit in each state's manual. Follow the preamble's 6-state sampling rule
per element, starting with the elements that have the most states. Expect two outcomes per element: PATTERN-CONFIRMED
(the manual chapter genuinely carries the group's eligibility rule → tell us the stronger pattern that would have matched,
e.g. the chapter heading vocabulary) or ABSENT-IN-CITED (the hit is a cross-reference, not the rule → say which document
family carries it). Cap at ~250 cells read; prioritise Medicaid over CHIP, and within Medicaid the eligibility-group and
income-methodology elements over administrative ones.

## Part C

Run note `docs/ingest-runs/2026-09-15-medicaid-chip.md`, decisions `docs/ingest-runs/2026-09-15-medicaid-chip-decisions.csv`,
draft PR.
