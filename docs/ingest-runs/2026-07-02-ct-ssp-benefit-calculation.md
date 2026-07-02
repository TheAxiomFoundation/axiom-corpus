# 2026-07-02 Connecticut SSP Benefit Calculation Corpus

## Scope

Extends the Connecticut State Supplement Program corpus with official DSS UPM
benefit-calculation sections needed to encode the final AABD SSP amount:

- UPM 6000, calculation of benefits.
- UPM 6000.01, calculation-related definitions.
- UPM 6005, comparing income and needs, including the AABD subtraction and
  spousal issuance rules.

These are Connecticut Department of Social Services UPM6 policy-manual sources.
They complement the already ingested income, eligibility, asset, and program
standards sources for the CT SSP parity path.

## Command

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-02-ct-ssp-upm-and-standards \
  --manifest manifests/us-ct-ssp-official-documents.yaml \
  --source-as-of 2026-07-02 \
  --expression-date 2026-07-02
```

## Result

- Jurisdiction/document class: `us-ct` / `policy`
- Source files: 14
- Provisions written: 28
- Coverage: complete

The DOC source snapshots are stored with the corpus artifacts and the signed
ingest manifest covers the regenerated source, inventory, provision, and
coverage files.
