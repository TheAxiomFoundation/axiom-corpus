# Belgium Cadastral-Income Indexation Ingest

Run date: 2026-07-03

Manifest:

- `manifests/be-cadastral-income-indexation-official-documents.yaml`

Command:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-03-be-cadastral-income-indexation \
  --manifest manifests/be-cadastral-income-indexation-official-documents.yaml \
  --source-as-of 2026-07-03
```

Scope:

- SPF Finances official guidance page for declaring non-occupied, non-let built immovable property.
- The page states the cadastral-income indexation formula and the 2025 and 2026 coefficients used with CIR 1992 article 518.
- SPF Finances official previous-year amount page, which states the 2024 coefficient.

Notes:

- CIR 1992 article 518 remains the statutory formula source.
- The official SPF Finances page supplies current annual coefficients that are not stated in the consolidated statutory text itself.
