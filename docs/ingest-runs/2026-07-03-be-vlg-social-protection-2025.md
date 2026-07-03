# 2026-07-03 Flemish Social Protection 2025 Corpus

## Scope

Snapshots the official Vlaamse Codex consolidated text for the Flemish Social
Protection implementing order as of 1 January 2025. This supplies the BE_2025
Article 68 premium base and indexation text for RuleSpec and EUROMOD oracle
comparison work.

The Moniteur ELI URL remains recorded as the legal-authority reference in the
manifest, while the extracted text uses the dated official consolidated
Vlaamse Codex print view.

## Command

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-03-be-vlg-social-protection-regulation-2025 \
  --manifest manifests/be-vlg-social-protection-regulation-2025-documents.yaml
```

## Result

- Regulation jurisdiction/document class: `be-vlg` / `regulation`
- Regulation source files: 1
- Regulation provisions written: 298
- Regulation coverage: complete

Key premium citation:

- `be-vlg/regulation/codex-vlaanderen/social-protection/implementation-order-2025/block-26`

## Statbel Health Index Source

Article 68 indexes the 2022-2025 base amounts using the health-index ratio
between April of the previous year and April 2020. The official Statbel
open-data workbook was therefore snapshotted as the upstream source for the
April 2020 and April 2024 health-index values used in the 2025 premium.

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-03-be-statbel-health-index \
  --manifest manifests/be-statbel-health-index-official-documents.yaml
```

Result:

- Statbel jurisdiction/document class: `be` / `guidance`
- Statbel source files: 1
- Statbel provisions written: 2
- Statbel coverage: complete

Key Statbel citation:

- `be/guidance/statbel/consumer-price-index-and-health-index/sheet-1`

The filtered sheet block records base-year 2013 rows:

- April 2020 health index: `110.22`
- April 2024 health index: `130.85`
