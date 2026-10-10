# California 2026 estimated-tax worksheet sources

This intake preserves the California Franchise Tax Board's official
tax-year-2026 Form 540-ES instructions and the official 2025 tax-computation
materials that those instructions incorporate. The dependency is deliberate
and narrow: this corpus scope supports the 2026 estimated-tax worksheet, not a
final tax-year-2026 Form 540 or Form 540NR liability calculation.

## 2026 Form 540-ES instructions

Official source:
<https://www.ftb.ca.gov/forms/2026/2026-540-es-instructions.pdf>

The retained three-page PDF has SHA-256
`3e67bc8f3dc6773cee6dab6e3d1b8d70ee03b8f91fbd581b5ad0e44ec49970bc`
and an FTB server last-modified date of December 18, 2025. The complete PDF is
normalized as one body-bearing child under
`us-ca/form/individual-income-tax/2026/540-es-instructions`.

The 2026 California Estimated Tax Worksheet publishes standard deductions of
$5,706 for single or married/RDP filing separately and $11,412 for
married/RDP filing jointly, head of household, or qualifying surviving
spouse/RDP. Worksheet line 4 instructs taxpayers to figure tax on worksheet
line 3 using the 2025 tax table for Form 540 or Form 540NR, while also
including any tax from FTB 3800 and FTB 3803.

Section D provides the Behavioral Health Services Tax worksheet. It subtracts
$1,000,000 from Form 540 line 19 taxable income or Form 540NR line 35
nonresident California-source taxable income, multiplies the positive excess
by 1%, and carries the result to estimated-tax worksheet line 17.

The existing body-bearing statutory provisions
`us-ca/statute/rtc/17041`, `us-ca/statute/rtc/17043`, and
`us-ca/statute/rtc/17073.5` retain the rate, additional-tax, and
standard-deduction authorities. The FTB instructions supply the
tax-year-specific administrative values and estimated-tax workflow.

## Incorporated 2025 computation materials

Official sources:

- <https://www.ftb.ca.gov/forms/2025/2025-540-taxtable.pdf>
- <https://www.ftb.ca.gov/forms/2025/2025-540-tax-rate-schedules.pdf>

The retained 2025 California Tax Table has SHA-256
`0414ffb02dbcd209966f5fe9bbdfeffd55816cc8d86a08501fd9ef7d79e7087d`.
The retained 2025 California Tax Rate Schedules have SHA-256
`ad70ee345aa7daf5788b64419e04280c76fbebd0c15856820ccea71f3534a8c6`.
Both complete PDFs are normalized into body-bearing children.

The official 2025 materials divide the lookup at $100,000 of taxable income.
The tax table applies at or below $100,000. Above $100,000, Schedules X, Y,
and Z publish the filing-status bracket formulas. Those schedules use rates
of 1%, 2%, 4%, 6%, 8%, 9.3%, 10.3%, 11.3%, and 12.3%.

These 2025 artifacts are retained only because 2026 Form 540-ES line 4 directs
their use. Their presence must not be read as a claim that the 2025 brackets
are the final tax-year-2026 return brackets. The scope also does not certify
exemption credits, special child-income calculations, nonresident proration,
alternative minimum tax, other credits, withholding, installment safe
harbors, or any other component needed for a complete final-return liability.

## Generation and publication boundary

The scopes are generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-23-ca-2026-form-540-es \
  --manifest manifests/us-ca-2026-form-540-es-instructions.yaml

uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-23-ca-2025-tax-materials-for-2026-estimates \
  --manifest manifests/us-ca-2025-tax-materials-for-2026-estimates.yaml
```

The protected signing wrapper creates a distinct signed ingest manifest for
each generated scope. No private signing material is read, printed, or
written by this ingestion session.
