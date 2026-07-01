# Brussels Housing Allowances Official-Document Ingest

Run date: 2026-07-01

Manifest:

- `manifests/be-bru-housing-allowances-official-documents.yaml`

Command:

```bash
uv run --extra dev axiom-corpus-ingest extract-belgian-eli \
  --base data/corpus \
  --version 2026-07-01-be-bru-housing-allowances \
  --manifest manifests/be-bru-housing-allowances-official-documents.yaml \
  --request-timeout 45
```

Result:

| Jurisdiction | Document class | Source files | Provisions | Coverage |
|---|---:|---:|---:|---:|
| `be-bru` | `regulation` | 2 | 69 | complete |

Total provisions written: 69.

Notes:

- Sources are official ejustice ELI pages for the Brussels-Capital Region
  Government orders of 15 July 2021 and 13 October 2022.
- The source URLs use Justel as the current consolidated locator and preserve
  the Moniteur belge / Belgisch Staatsblad ELI legal-authority URLs in source
  metadata.
- The generated corpus artifacts are under
  `data/corpus/{sources,provisions,inventory,coverage}/be-bru/regulation/2026-07-01-be-bru-housing-allowances.*`
  and remain ignored by git like the rest of downloaded corpus data.
