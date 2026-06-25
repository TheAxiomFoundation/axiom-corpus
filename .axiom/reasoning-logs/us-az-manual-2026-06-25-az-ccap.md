US Arizona CCAP manual corpus ingest reasoning

Date: 2026-06-25

Goal

Make the official Arizona DES Child Care Assistance sources needed for active
PolicyEngine parity available to Axiom encoders without hand-writing corpus
rows.

Source selection

- Used official Arizona Department of Economic Security Child Care Assistance
  pages and PDFs because PolicyEngine's `az_ccap` surface depends on Arizona
  CCAP eligibility, income, copay, reimbursement, and provider rules.
- Included the DES child care assistance application page, FFY 2026 gross
  monthly income eligibility and fee schedule, maximum reimbursement rates, and
  child care provider registration agreement.
- Live DES URLs returned Cloudflare challenge pages to unattended HTTP clients
  on 2026-06-25. Used Internet Archive captures of the same official URLs,
  matching the existing Arizona DES FAA5 corpus pattern.

Method

- Added `manifests/us-az-ccap-manual.yaml` with four official DES sources and
  stable citation paths under `us-az/manual/des/ccap`.
- Ran:
  `uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-06-25-az-ccap --manifest manifests/us-az-ccap-manual.yaml`
- No provision JSONL rows or source snapshots were edited by hand.

Result

- Generated 4 source snapshots.
- Generated 82 normalized provision rows.
- Coverage reported `coverage_complete: true`, with 82 sources matched, 82
  provisions, zero missing rows, and zero extra rows.

Notes for encoders

- The relevant citation paths are
  `us-az/manual/des/ccap/how-to-apply`,
  `us-az/manual/des/ccap/income-chart-ffy2026`,
  `us-az/manual/des/ccap/reimbursement-rates`, and
  `us-az/manual/des/ccap/provider-registration-agreement`.
- Use the regulation scope
  `us-az/regulation/aac/title-6/chapter-5/article-49` for codified Article 49
  Child Care Assistance rules.
