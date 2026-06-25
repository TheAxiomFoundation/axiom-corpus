US Georgia TANF manual corpus ingest reasoning

Date: 2026-06-25

Goal

Make the official Georgia DFCS TANF manual provisions needed for active
PolicyEngine parity available to Axiom encoders without hand-writing corpus
rows.

Source selection

- Used Georgia Department of Human Services PAMMS pages for the active TANF
  policy manual because PolicyEngine's Georgia TANF implementation cites these
  pages and they expose stable official HTML.
- Scoped the initial ingest to the PE-relevant cash-assistance financial rules:
  1525 Income, 1605 Basic Budgeting, 1615 Deductions, and Appendix A TANF
  Financial Standards.
- Did not ingest the Georgia SOS rule pages in this run. The live pages load
  rule text through an Ajax endpoint that is not supported by the generic
  official-document extractor and should be handled by a dedicated Georgia
  rule adapter if needed.

Method

- Added `manifests/us-ga-tanf-manual.yaml` with four official PAMMS HTML
  documents and `article.doc` extraction, matching the existing Georgia SNAP
  and SSP official-document manifest pattern.
- Ran:
  `uv run axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-06-25-ga-tanf --manifest manifests/us-ga-tanf-manual.yaml`
- No provision JSONL rows or source HTML snapshots were edited by hand.

Result

- Generated 4 source HTML snapshots.
- Generated 47 normalized provision rows.
- Coverage reported `coverage_complete: true`, with 47 sources matched, 47
  provisions, zero missing rows, and zero extra rows.

Notes for encoders

- The relevant formula/table rows are under `us-ga/manual/dfcs/tanf/1525`,
  `us-ga/manual/dfcs/tanf/1605`, `us-ga/manual/dfcs/tanf/1615`, and
  `us-ga/manual/dfcs/tanf/appendix-a`.
- Current Appendix A, as of this ingest, contains the cash-assistance table
  through AU size 11, additional-member increments, and the $1,000 resource
  limit.
