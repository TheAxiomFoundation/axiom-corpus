# Maine tax-year-2026 individual income-tax rates

This intake retains one official Maine Revenue Services PDF:

`https://www.maine.gov/revenue/sites/maine.gov.revenue/files/2026-05/ind_tax_rate_sched_2026_rev.pdf`

The retained file has SHA-256
`64946a135ef18e8a0085fb47b67e99968467fd0b8d8932ea68d9f3c7560d6d80`.
The PDF identifies Maine Revenue Services, Income/Estate Tax Division as its
preparer and states that it was revised May 20, 2026.

## Scope

The generic official-document adapter retains the one-page PDF as one
body-bearing child provision beneath its document container. The provision
preserves all three graduated rates and the complete filing-status schedules:

- single and married filing separately: $27,400 and $64,850;
- head of household: $41,100 and $97,300; and
- married filing jointly and surviving spouse: $54,850 and $129,750.

The retained body also preserves the published bracket base amounts and the
rate sequence of 5.8%, 6.75%, and 7.15%.

The same official schedule's Note (1) establishes a 2% surcharge for tax years
beginning on or after January 1, 2026. The surcharge applies to the portion of
Maine taxable income greater than $1,000,000 for single filers, $750,000 for
married-separate filers, and $1,500,000 for married-joint and head-of-household
filers. The note says inflation adjustment of those thresholds begins for tax
years beginning on or after January 1, 2027.

Coverage is complete at two inventory citations and two normalized
provisions: the source document container and its body-bearing child.

The existing body-bearing `us-me/statute/36/5111/block-2` provision in statute
scope `2026-07-13-recovery` remains background authority for the underlying
statutory rate tables. This guidance intake supplies the Department's
tax-year-2026 indexed schedules and surcharge instruction. It supports only a
schedule calculation after Maine taxable income and filing status have already
been determined. It does not establish taxable income, deductions, exemptions,
credits, withholding, residency, nonresident allocation, tax-table
substitution, RuleSpec semantics, PolicyEngine parity, or final-return
liability.

No secondary source or mutable forms-index page is retained. The dated,
year-specific official PDF is the sole source artifact in this scope.

## Generation

The scope is generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-23-me-individual-income-tax-rates-2026 \
  --manifest manifests/us-me-individual-income-tax-rates-2026.yaml
```

Repeating the extraction produced identical source, inventory, provision, and
coverage hashes. The protected signing wrapper creates the signed ingest
manifest under `.axiom/ingest-manifests/us-me/guidance/`; no private signing
material is read, printed, or written by the ingestion session.
