# Hawaii Form N-11 capital-gains worksheet

This scope retains the official Hawaii Department of Taxation tax-year-2025
Form N-11 instructions from the immutable year-specific URL:

`https://files.hawaii.gov/tax/forms/2025/n11ins.pdf`

The retained PDF has SHA-256
`7160595e466b376ba9c14da1540d21532be9e05d48d01d877f5d953c85e4e4d4`.
Its printed page 33 (PDF page 35) is sliced with the generic official-document
adapter's anchored `page_windows` support. The normalized worksheet is:

`us-hi/form/individual-income-tax/2025/n-11-instructions/capital-gains-tax-worksheet`

The window stops before the neighboring Other State and Foreign Tax Credit
Worksheet. It preserves the complete capital-gain calculation, including the
smaller of Hawaii net long-term capital gain and Hawaii net capital gain,
investment-interest adjustment, ordinary-income base, 7.25 percent alternative
tax, and final comparison with ordinary tax.

## 2026 use and corrected amounts

The 2025 worksheet is a structural source only for the 2026 RuleSpec. Hawaii
DOTAX's official Form Errors page, current as of April 22, 2026, says its
printed eligibility and line-12 amounts are incorrect. For tax year 2026 the
correct thresholds are $48,000 for single or married filing separately,
$72,000 for head of household, and $96,000 for joint or qualifying surviving
spouse. These are the ceilings of the rates below 7.25 percent in the HRS
235-51(a)-(c) schedules applicable after December 31, 2024. HRS 235-51(f)
supplies the 7.25 percent alternative rate.

The authoritative 2026 amounts remain bound to corpus citation
`us-hi/statute/235-51` in scope
`us-hi/statute/2026-07-16-pit-east-us-hi-volume-04-chapter-235`. The form
provision metadata records the structural-only limitation, corrected values,
statutory scope, and DOTAX correction URL so consumers cannot treat the stale
printed amounts as 2026 parameters.

## Generation and release

The scope was generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-22-hi-2025-n11-capital-gain-worksheet \
  --manifest manifests/us-hi-2025-n11-capital-gain-worksheet.yaml
```

Coverage is complete at two inventory citations and two normalized provisions.
The protected signing wrapper produced the signed ingest manifest at
`.axiom/ingest-manifests/us-hi/form/2026-07-22-hi-2025-n11-capital-gain-worksheet.json`.
No private signing material was read or written by the ingestion session.

The successor selector
`us-rulespec-2026-07-22-hi-capital-gain-current` adds this form scope to
`us-rulespec-2026-07-22-current-la-status-fix` and retains the complete Hawaii
chapter 235 statutory scope for the 2026 amounts.
