# South Dakota personal income-tax zero-liability authority (2026-07-24)

This scope preserves the South Dakota Department of Revenue's official January
2026 statement that South Dakota does not have a personal income tax. Because
the publication is expressly dated January 2026 and describes the state's
current tax system, it supports the complete tax-year-2026 annual resident
personal income-tax result for a natural person through the pre-credit tax
stage.

The guide does not certify a complete tax-year-2026 nonrefundable-credit or
refundable-credit inventory, credit ordering, or signed net-liability surface.
Those downstream stages must remain explicitly source held rather than being
inferred from the no-personal-income-tax statement.

The source-backed pre-credit zero is limited to personal income tax. The guide
separately notes that businesses may be subject to other taxes, and South
Dakota's bank franchise and other business or entity taxes remain outside this
scope. Payments, filing administration, local taxes, and nonresident
allocation are also outside scope.

Artifacts are generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-24-sd-personal-income-tax-zero-liability \
  --manifest manifests/us-sd-2026-personal-income-tax-zero-liability.yaml
```

The archived source is the complete official guide PDF. The normalized
single-block provision preserves the extracted guide text, including the
operative no-personal-income-tax statement.
