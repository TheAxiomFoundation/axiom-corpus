US Arizona Administrative Code Article 49 corpus ingest reasoning

Date: 2026-06-25

Goal

Make Arizona Administrative Code Title 6, Chapter 5, Article 49 available to
Axiom encoders for Arizona Child Care Assistance parity without hand-writing
corpus rows.

Source selection

- Used the official Arizona Secretary of State PDF for Title 6, Chapter 5.
- Article 49 is the codified Child Care Assistance article and contains
  definitions, access rules, eligibility conditions, income rules, approvals,
  waiting list rules, authorization rules, reimbursement provisions, and
  termination/appeal provisions.
- The live AZSOS URL returned a Cloudflare challenge page to unattended HTTP
  clients on 2026-06-25. Used the Internet Archive capture of the same official
  URL, matching the Arizona DES archived-source pattern.

Method

- Added `manifests/us-az-ccap-regulation.yaml` for the official AZSOS Title 6,
  Chapter 5 PDF and citation path
  `us-az/regulation/aac/title-6/chapter-5/article-49`.
- Added generic `end_page` support to the official-document PDF line filter so
  this manifest can extract only Article 49 pages 20 through 43 instead of the
  full 126-page chapter.
- Ran:
  `uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-06-25-az-aac-title-6-chapter-5-article-49 --manifest manifests/us-az-ccap-regulation.yaml`
- No provision JSONL rows or source snapshots were edited by hand.

Result

- Generated 1 source PDF snapshot.
- Generated 25 normalized provision rows: the Article 49 container plus 24
  `R6-5-49xx` sections.
- Coverage reported `coverage_complete: true`, with 25 sources matched, 25
  provisions, zero missing rows, and zero extra rows.

Notes for encoders

- The main citation path is
  `us-az/regulation/aac/title-6/chapter-5/article-49`.
- Section citation paths include
  `us-az/regulation/aac/title-6/chapter-5/article-49/R6-5-4901` through
  `us-az/regulation/aac/title-6/chapter-5/article-49/R6-5-4924`.
