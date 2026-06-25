US Georgia CAPS manual corpus ingest reasoning

Date: 2026-06-25

Goal

Make the official Georgia DECAL CAPS sources needed for active PolicyEngine
parity available to Axiom encoders without hand-writing corpus rows.

Source selection

- Used official Georgia Department of Early Care and Learning CAPS PDFs because
  PolicyEngine's Georgia CAPS implementation cites the CAPS policy manual and
  appendices for eligibility, income limits, reimbursement rates, and family
  fees.
- Included the 2025-2027 CCDF State Plan because CAPS is funded and governed
  through CCDF and the plan documents Georgia's active child care assistance
  policy commitments.
- Confirmed all five source URLs were reachable by unattended HTTP requests
  before ingest.

Method

- Added `manifests/us-ga-caps-manual.yaml` with five official DECAL PDFs and
  citation paths for the policy manual, Appendix A income limits, Appendix C
  reimbursement rates, Appendix D family fee chart, and the 2025-2027 CCDF
  State Plan.
- Ran:
  `uv run axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-06-25-ga-caps --manifest manifests/us-ga-caps-manual.yaml`
- No provision JSONL rows or source PDF snapshots were edited by hand.

Result

- Generated 5 source PDF snapshots.
- Generated 506 normalized provision rows.
- Coverage reported `coverage_complete: true`, with 506 sources matched, 506
  provisions, zero missing rows, and zero extra rows.

Notes for encoders

- The relevant citation paths are
  `us-ga/manual/decal/caps/policy-manual`,
  `us-ga/manual/decal/caps/appendix-a-income-limits`,
  `us-ga/manual/decal/caps/appendix-c-reimbursement-rates`,
  `us-ga/manual/decal/caps/appendix-d-family-fee-chart`, and
  `us-ga/manual/decal/caps/ccdf-state-plan-2025-2027`.
- The manual contains eligibility, application, family-fee, and purchase-of-care
  rules. Appendix A contains maximum income limits by family size. Appendix C
  contains reimbursement rates by provider and care category. Appendix D
  contains the family fee assessment chart.
