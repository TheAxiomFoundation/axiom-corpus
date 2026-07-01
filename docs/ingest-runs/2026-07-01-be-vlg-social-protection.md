# 2026-07-01 Flemish Social Protection Corpus

## Scope

Snapshots official Flemish Social Protection sources for the annual zorgpremie
surface:

- Flemish Social Protection decree of 18 May 2018 from Vlaamse Codex.
- Flemish Government implementing order of 30 November 2018 from Vlaamse Codex.

The Moniteur ELI URLs remain recorded as legal-authority references in the
manifests, while the extracted text uses the current official consolidated
Vlaamse Codex print views.

## Commands

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-01-be-vlg-social-protection-decree \
  --manifest manifests/be-vlg-social-protection-decree-documents.yaml

uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-01-be-vlg-social-protection-regulation \
  --manifest manifests/be-vlg-social-protection-regulation-documents.yaml
```

## Result

- Decree jurisdiction/document class: `be-vlg` / `statute`
- Decree source files: 1
- Decree provisions written: 92
- Decree coverage: complete
- Regulation jurisdiction/document class: `be-vlg` / `regulation`
- Regulation source files: 1
- Regulation provisions written: 297
- Regulation coverage: complete

Key premium citations:

- `be-vlg/statute/codex-vlaanderen/social-protection/decree-2018-05-18/block-22`
- `be-vlg/statute/codex-vlaanderen/social-protection/decree-2018-05-18/block-23`
- `be-vlg/regulation/codex-vlaanderen/social-protection/implementation-order/block-25`
