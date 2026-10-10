# Louisiana 2026 individual estimated-tax instructions

This intake retains the official Louisiana Department of Revenue tax-year-2026
Form IT-540ESi estimated-tax instructions and worksheet.

Official source:
<https://dam.ldr.la.gov/taxforms/IT540ESi-2026.pdf>

Official LDR form index:
<https://revenue.louisiana.gov/tax-forms/individuals/?tax_type=individual&years=2026>

The retained two-page PDF has SHA-256
`5733a329213809222d304e87ab6ce17200790843490fc21240ce415ceb5947dd`.
The generic official-document adapter snapshots the complete PDF and produces
one document container plus one body-bearing provision at
`us-la/form/individual-income-tax/2026/it-540es-instructions/document-1`.
Coverage is complete at two inventory citations and two normalized provisions.

Page 2 publishes the following filing-status amounts:

- single: $12,875;
- married filing separately: $12,875;
- married filing jointly: $25,750;
- head of household: $25,750; and
- qualifying surviving spouse: $25,750.

The worksheet starts with estimated 2026 federal adjusted gross income,
subtracts estimated exempt income and the applicable Louisiana estimated
standard deduction, and multiplies the resulting estimated Louisiana taxable
income by 3%. Page 1 also publishes estimated-payment filing thresholds of
$1,000 for a single filer and $2,000 for joint filers.

This source is deliberately limited to estimated tax. It directs taxpayers to
use the 2025 Form IT-540 and instructions as a guide, and worksheet lines 6 and
7 refer to estimated 2025 nonrefundable and refundable credits rather than
publishing tax-year-2026 credit rules. On the source-as-of date, the official
LDR individual-form index lists the 2026 IT-540ES materials but only a
tax-year-2025 annual resident Form IT-540. Accordingly, this intake does not
certify a final tax-year-2026 resident return, complete deductions, or complete
credits, and it does not assert RuleSpec semantics or PolicyEngine parity.

The scope is generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-23-la-2026-it-540es-instructions \
  --manifest manifests/us-la-2026-it-540es-instructions.yaml
```

Repeating extraction must reproduce identical source, inventory, provision,
and coverage hashes. The protected signing wrapper creates the signed ingest
manifest without exposing private signing material.
