# Kentucky 2026 individual income-tax sources (2026-07-22)

This intake replaces reliance on the body-empty canonical aliases in the
older `2026-07-13-recovery` Kentucky statute scope with exact, body-bearing
snapshots of the two official Kentucky Revised Statutes sections needed for a
narrow tax-year-2026 individual income-tax calculation:

- KRS 141.020, whose subsection (2)(f) applies a 3.5 percent rate to net
  income for taxable years beginning on or after January 1, 2026; and
- KRS 141.081, which establishes the optional individual standard deduction
  and its annual CPI-U adjustment mechanism.

KRS 141.081 does not publish the resulting 2026 dollar amount. The separate
official Kentucky Department of Revenue Form 740-ES instructions state that
the 2026 standard deduction is $3,360. The worksheet also directs individuals
to multiply estimated net income by 3.5 percent. No value is inferred from an
inflation series or from a secondary source.

Official sources:

- <https://apps.legislature.ky.gov/law/statutes/statute.aspx?id=56339>
- <https://apps.legislature.ky.gov/law/statutes/statute.aspx?id=29067>
- <https://revenue.ky.gov/Forms/740-ES%20Instructions%20%282025%29.pdf>

The two deterministic extraction commands are:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-22-individual-income-tax \
  --manifest manifests/us-ky-2026-individual-income-tax-statutes.yaml

uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-740-es \
  --manifest manifests/us-ky-2026-740-es.yaml
```

The statute scope intentionally preserves the complete official PDFs rather
than reconstructing excerpts from the older combined HTML recovery snapshot.
The form scope preserves the complete official DOR estimated-tax instructions
and their published worksheet parameters. The news release announcing the
same deduction was audited but not retained because its SharePoint response
contains changing request state and is therefore not byte-deterministic.

The retained source SHA-256 digests are:

- KRS 141.020: `ba8f7b25f40ff55012f8e1713d4b4b58fcee9ac5a14b116e7b77c9c6a27b6777`;
- KRS 141.081: `15191d4bb195e64d4d318dc09da270f4cb09cbcaeea997a1a72afd8d2db67084`;
  and
- 2026 Form 740-ES instructions: `c487e17c3dfee562b2d4e8501175d8057c81d4b8ab7a54d2c7bc885e352cd4ad`.

The statute scope has four inventory citations and four normalized provisions.
The form scope has two inventory citations and two normalized provisions.
Both coverage reports are complete. Repeating each extraction produced the
same source, inventory, provision, and coverage hashes.

Scope limitation: these artifacts support only the statutory 3.5 percent rate,
its tax-year applicability, the statutory indexing authority, and DOR's
published $3,360 standard deduction. They do not encode federal-to-Kentucky
income adjustments, itemized-deduction elections, credits, nonresident rules,
rounding, final-return liability, RuleSpec semantics, or PolicyEngine parity.
