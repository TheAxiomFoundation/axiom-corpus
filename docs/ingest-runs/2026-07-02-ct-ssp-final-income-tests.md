# 2026-07-02 Connecticut SSP Final Income Tests Corpus

## Scope

Extends the Connecticut State Supplement Program corpus with official DSS UPM
sections needed for the final AABD income and benefit calculation path:

- UPM 5000, general treatment of income.
- UPM 5045.10, applied income calculation method.
- UPM 5050.13, treatment of Social Security, SSI, and VA benefits.
- UPM 5520.10, AABD gross and applied income eligibility tests.

These are state policy manual sources from the Connecticut Department of Social
Services and sit downstream of Conn. Gen. Stat. section 17b-600, which is
already encoded for the statutory SSP income-cap authority.

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
- Source files: 11
- Provisions written: 22
- Coverage: complete

The DOC source snapshots are stored with the corpus artifacts and the signed
ingest manifest covers the regenerated source, inventory, provision, and
coverage files.
