# 2026-07-04 Flemish Jobbonus 2025 Corpus

## Scope

Snapshots the official Vlaamse Codex consolidated text for the Flemish
jobbonus decree and its implementing order. The decree supplies the statutory
beneficiary categories and eligibility framework; the dated 1 January 2025
implementing order supplies the BE_2025 wage thresholds, amount formula,
proration rules, small-payment suppression, and fixed top-up.

The Moniteur ELI URLs remain recorded as legal-authority references in the
manifests, while the extracted text uses the official consolidated Vlaamse
Codex print views.

## Commands

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-04-be-vlg-jobbonus-decree \
  --manifest manifests/be-vlg-jobbonus-decree-documents.yaml

uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-04-be-vlg-jobbonus-regulation-2025 \
  --manifest manifests/be-vlg-jobbonus-implementation-order-2025-documents.yaml
```

## Result

- Decree jurisdiction/document class: `be-vlg` / `statute`
- Decree source files: 1
- Decree provisions written: 11
- Regulation jurisdiction/document class: `be-vlg` / `regulation`
- Regulation source files: 1
- Regulation provisions written: 15
- Coverage: complete

Key jobbonus citations:

- `be-vlg/statute/codex-vlaanderen/jobbonus/decree-2022-05-20/block-4`
- `be-vlg/regulation/codex-vlaanderen/jobbonus/implementation-order-2025/block-5`
- `be-vlg/regulation/codex-vlaanderen/jobbonus/implementation-order-2025/block-6`
