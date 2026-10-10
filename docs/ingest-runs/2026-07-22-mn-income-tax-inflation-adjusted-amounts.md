# Minnesota tax-year-2026 income-tax bracket thresholds

This intake retains one official Minnesota Department of Revenue PDF:

`https://www.revenue.state.mn.us/sites/default/files/2025-12/inflation-adjusted-amounts-2026.pdf`

The retained file has SHA-256
`db216e8d9c0db86bb381cd4fbe3e338b933eae66e833e9dbe57b27c483557b8b`.
The PDF identifies Minnesota Department of Revenue, Tax Research as its author
and states that all income-tax amounts in its table are for tax year 2026.

## Scope

The generic official-document adapter uses an anchored PDF page window from
the `290.06, Subd. 2c` label on PDF page 2 through, but not including, the
`290.067, Subd. 1` label on PDF page 3. It produces one document container and
four body-bearing filing-status provisions:

- married joint or surviving spouse: $48,700, $193,480, and $337,930;
- married separate: $24,350, $96,740, and $168,965;
- single: $33,310, $109,430, and $203,150; and
- head of household: $41,010, $164,800, and $270,060.

Each triplet is the published second-, third-, and fourth-bracket threshold.
The extraction retains the PDF's statutory-year annotations instead of
rewriting its table. Coverage is complete at five inventory citations and five
normalized provisions.

The existing body-bearing `us-mn/statute/290.06/block-12` provision in statute
scope `2026-07-13-recovery` remains the authority for the four rates and
schedule structure. The adjacent `us-mn/statute/290.06/block-13` provision is
the authority for annual indexing, rounding, and the married-separate bracket
rule. This guidance intake supplies only the Department's resulting
tax-year-2026 threshold amounts. It does not infer or certify taxable income,
tax-table substitution, alternative or net investment income taxes, credits,
nonresident allocation, RuleSpec semantics, PolicyEngine parity, or
final-return liability.

No press release or mutable live page is retained. The year-specific official
PDF is the sole source artifact in this scope.

## Generation

The scope is generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-22-mn-income-tax-inflation-adjusted-amounts-2026 \
  --manifest manifests/us-mn-income-tax-inflation-adjusted-amounts-2026.yaml
```

Repeating the extraction produced identical source, inventory, provision, and
coverage hashes. The protected signing wrapper creates the signed ingest
manifest under `.axiom/ingest-manifests/us-mn/guidance/`; no private signing
material is read, printed, or written by the ingestion session.
