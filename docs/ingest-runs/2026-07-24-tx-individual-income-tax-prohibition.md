# Texas individual income-tax prohibition authority (2026-07-24)

This scope preserves the current official Texas constitutional authority for
the tax-year-2026 annual resident individual-income-tax result through the
pre-credit tax stage.

Article VIII, section 24-a prohibits the legislature from imposing a tax on
the net incomes of individuals, including an individual's share of partnership
and unincorporated-association income. Section 24-b, added November 4, 2025,
separately prohibits a tax on realized or unrealized capital gains of an
individual, family, estate, or trust. Section 24-b preserves ad valorem, sales,
and use taxes; those taxes are outside this individual-income-tax scope.

The official source print was rendered June 14, 2026 and therefore contains
the operative constitutional text for the full 2026 tax year. The resulting
source-backed zero is limited to Texas resident individual net-income tax
before credits. The constitutional provisions do not certify a complete
tax-year-2026 nonrefundable-credit or refundable-credit inventory, credit
ordering, or signed net-liability surface. Those downstream stages remain
explicitly source held in RuleSpec.

The scope does not cover franchise or other business and entity taxes,
payments, filing administration, local taxes, or nonresident allocation.

Artifacts are generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-24-tx-individual-income-tax-prohibition \
  --manifest manifests/us-tx-2026-individual-income-tax-prohibition.yaml
```

The retained official PDF is the complete Texas Constitution print. Extraction
is limited to PDF pages 232–233 and emits separate normalized provisions for
Article VIII, sections 24-a and 24-b.
