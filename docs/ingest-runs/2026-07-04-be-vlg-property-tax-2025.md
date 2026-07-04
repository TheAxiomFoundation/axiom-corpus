# 2026-07-04 Flemish Property-Tax 2025 Article Versions

## Scope

Snapshots the 2025-effective Vlaamse Codex Fiscaliteit article versions needed
for EUROMOD BE_2025 immovable-withholding comparisons:

- Article 2.1.4.0.1 version 1433495: 2023-2025 Flemish base immovable
  withholding rates.
- Article 2.1.4.0.2 version 1302348: authorization for provincial, municipal,
  and agglomeration additional centimes on immovable withholding.

## Command

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-04-be-vlg-property-tax-2025 \
  --manifest manifests/be-vlg-property-tax-2025-official-documents.yaml
```

## Result

- Jurisdiction: `be-vlg`
- Document class: `statute`
- Source files: 2
- Provisions written: 2
- Coverage: complete
- Coverage path:
  `data/corpus/coverage/be-vlg/statute/2026-07-04-be-vlg-property-tax-2025.json`
