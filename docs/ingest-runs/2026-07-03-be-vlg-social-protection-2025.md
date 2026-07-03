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
