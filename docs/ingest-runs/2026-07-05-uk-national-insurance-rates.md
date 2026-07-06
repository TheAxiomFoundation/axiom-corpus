# UK National Insurance rates guidance ingest reasoning

Impact basis:

- rulespec-uk encodes SSCBA 1992 s.13 Class 3 voluntary contributions
  (`uk/statutes/ukpga/1992/4/13.yaml`, merged as rulespec-uk#82) with the
  weekly amount grounded verbatim to the legislation.gov.uk s.13(1) corpus
  text, which reads "the amount of a Class 3 contribution shall be £17.75".
  That is the 2025-26 figure: the annual administrative re-rating to £18.40
  for 2026-27 is made by order and is not consolidated into the s.13 base
  text on legislation.gov.uk. The corpus therefore carried no official text
  containing the 2026-27 Class 3 weekly amount, so rulespec-uk could not add
  a proof-grounded 2026-04-06 parameter version. Class 3 has no oracle
  (PolicyEngine models `ni_class_3` as a frozen input), so this is a
  currency/completeness gap, not a parity gap.

Official sources (primary official only):

- HM Revenue and Customs, "Rates and allowances: National Insurance
  contributions", GOV.UK official publication page, last updated
  2026-04-06. The Class 3 section carries the verbatim per-week rate table:
  "£ per week 2026 to 2027 2025 to 2026 2024 to 2025 2023 to 2024 Class 3
  rate £18.40 £17.75 £17.45 £17.45". This is the same GOV.UK guidance
  pattern as the existing `uk/guidance/govuk/student-loan-repayments`
  scope (corpus PR #88).

Verification:

- The 2026-27 column value £18.40 is cross-checked arithmetically by the
  page's own "Monthly Direct Debit payments for 2026 to 2027" table
  (block-12): 4-week months collect £73.60 = 4 x £18.40 and 5-week months
  collect £92.00 = 5 x £18.40, for every payment date from 8 May 2026 to
  9 April 2027.
- The 2025-26 column value £17.75 matches the legislation.gov.uk s.13(1)
  current expression already in the corpus
  (`uk/statute/ukpga/1992/4/13`), corroborating that the page's per-year
  columns align with the consolidated statute for the year the statute
  text reflects.
- Block-13 states "There will be some new National Insurance rates and
  thresholds from 6 April 2026", grounding the 2026-04-06 effective date
  alongside the "2026 to 2027" tax-year column label.

Scope:

- `uk/guidance` version `2026-07-05-uk-national-insurance-rates`: one
  document (`uk/guidance/govuk/national-insurance-rates/rates-and-allowances`)
  with 14 heading-segmented blocks covering Class 1 thresholds and rates,
  Class 2/Class 4, Class 3 (block-11 carries the money atoms), the Class 3
  Direct Debit schedule (block-12), and pointers to historical rates.
- The full page is ingested (not just the Class 3 section) because the same
  page is the canonical HMRC per-year rates surface for every NI class; the
  additional blocks give future encodes (Class 1 thresholds, Class 2 small
  profits threshold, Class 4 limits) the same grounding surface without a
  re-ingest under a different version.

Intended consumer:

- rulespec-uk s.13 `class_3_weekly_contribution_amount`: a 2026-04-06
  version with formula 18.40 grounded to
  `uk/guidance/govuk/national-insurance-rates/rates-and-allowances/block-11`
  (excerpt "Class 3 rate £18.40"), keeping the 2025-04-06 version grounded
  to the s.13(1) statute text.

Publication note:

- Supabase load-supabase and R2 sync-r2 are deliberately not run in this
  branch; the maintainer publication sequence in
  docs/agent-ingestion-runbook.md applies after merge.
