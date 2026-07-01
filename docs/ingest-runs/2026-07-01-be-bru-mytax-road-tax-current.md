# 2026-07-01 Brussels MyTax Road-Tax Corpus

## Scope

Snapshots the Brussels Fiscality MyTax public road-tax tariff panel as
retrieved on 1 July 2026 for detailed car and motorcycle tax-on-entry-into-
service tables.

The upstream Code des taxes assimilees aux impots sur les revenus is already
captured in the Belgian vehicle-tax code locator run. This run captures the
official public Brussels Fiscality tariff table used for current indexed
amounts after that legal-base check.

## Command

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-01-be-bru-mytax-road-tax-current \
  --manifest manifests/be-bru-mytax-road-tax-current-documents.yaml
```

## Result

- Jurisdiction: `be-bru`
- Document class: `guidance`
- Source files: 1
- Provisions written: 16
- Coverage: complete
- Coverage path:
  `data/corpus/coverage/be-bru/guidance/2026-07-01-be-bru-mytax-road-tax-current.json`

## Notes

The MyTax page still displays a stale validity sentence referring to tariffs
valid from 1 July 2025 through 30 June 2026. The amount tables retrieved on
1 July 2026 contain the indexed 2026 values, matching the current Brussels
Fiscality public sheets for road-tax amounts effective from 1 July 2026.
