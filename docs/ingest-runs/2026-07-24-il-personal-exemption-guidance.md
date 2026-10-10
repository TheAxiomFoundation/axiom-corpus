# Illinois tax-year-2026 personal exemption guidance

This scope retains the Illinois Department of Revenue's official tax-year-2026
personal exemption guidance. IDOR Answer 851 supplies the year-specific $2,925
amount per exemption, the dependent limitation, the additional $1,000
allowances for age 65 or older and blindness, and the federal adjusted gross
income ceilings of $500,000 for a joint return and $250,000 for all other
returns.

The guidance complements 35 ILCS 5/204. It is kept in a separate `guidance`
scope so the source class remains honest and so the year-specific
administrative parameter is not presented as statutory text.

Artifacts were generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-24-il-personal-exemption-guidance \
  --manifest manifests/us-il-2026-personal-exemption-guidance.yaml
```

The result contains five normalized blocks. Inventory, provision, and coverage
counts are each six, with no missing or extra citation paths. The protected
signing wrapper produced the signed ingest manifest at
`.axiom/ingest-manifests/us-il/guidance/2026-07-24-il-personal-exemption-guidance.json`.
No private signing material was read or written by the ingestion session.
