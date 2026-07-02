# 2026-07-02 Belgium Cadastral-Income Index Corpus

## Scope

Snapshots the official SPF Finances cadastral-income page that publishes the
current annual index coefficients used with CIR 1992 Article 518.

Legal source already present in corpus:

- `be/statute/fisconetplus/cir92/revenus-2025/page-721`: CIR 1992 Article 518
  establishes cadastral-income indexation for Article 255 immovable
  withholding, the CPI-ratio coefficient formula, and euro rounding.

Supporting current-value source added by this run:

- `be/guidance/spf-finances/cadastral-income/definition-usage`: official SPF
  Finances page listing the current cadastral-income index coefficients for
  revenue years 2024, 2025, and 2026.

## Command

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-02-be-cadastral-income-index \
  --manifest manifests/be-cadastral-income-index-official-documents.yaml
```

## Result

- Jurisdiction: `be`
- Document class: `guidance`
- Source files: 1
- Provisions written: 10
- Coverage: complete
- Coverage path:
  `data/corpus/coverage/be/guidance/2026-07-02-be-cadastral-income-index.json`

Key citation path:

- `be/guidance/spf-finances/cadastral-income/definition-usage/block-3`
  contains the `Indexation annuelle` block with the 2024, 2025, and 2026
  cadastral-income index coefficients and the note that, for immovable
  withholding, the assessment year equals the revenue year.

The extractor wrote generated corpus artifacts under `data/corpus/`:

- `data/corpus/inventory/be/guidance/2026-07-02-be-cadastral-income-index.json`
- `data/corpus/provisions/be/guidance/2026-07-02-be-cadastral-income-index.jsonl`
- `data/corpus/sources/be/guidance/2026-07-02-be-cadastral-income-index/`
