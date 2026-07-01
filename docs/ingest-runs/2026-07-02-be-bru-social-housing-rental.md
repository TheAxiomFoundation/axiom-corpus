# Brussels Social-Housing Rental Official-Document Ingest

Run date: 2026-07-02

Manifest:

- `manifests/be-bru-social-housing-rental-official-documents.yaml`

Command:

```bash
uv run --extra dev axiom-corpus-ingest extract-belgian-eli \
  --base data/corpus \
  --version 2026-07-02-be-bru-social-housing-rental \
  --manifest manifests/be-bru-social-housing-rental-official-documents.yaml \
  --request-timeout 45
```

Result:

| Jurisdiction | Document class | Source files | Provisions | Coverage |
|---|---:|---:|---:|---:|
| `be-bru` | `regulation` | 1 | 141 | complete |

Total provisions written: 141.

Notes:

- Source is the official ejustice ELI page for the Brussels-Capital Region
  Government order of 26 September 1996 organizing rental of dwellings managed
  by the Brussels Regional Housing Company or public-service real-estate
  companies.
- The source URL uses Justel as the current consolidated locator and preserves
  the Moniteur belge / Belgisch Staatsblad ELI legal-authority URL in source
  metadata.
- The generated corpus artifacts are under
  `data/corpus/{sources,provisions,inventory,coverage}/be-bru/regulation/2026-07-02-be-bru-social-housing-rental.*`
  and remain ignored by git like the rest of downloaded corpus data.
