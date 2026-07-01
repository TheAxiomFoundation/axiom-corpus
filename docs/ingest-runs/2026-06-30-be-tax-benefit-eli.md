# Belgium Tax-Benefit ELI Ingest

Run date: 2026-06-30

Manifest:

- `manifests/be-tax-benefit-eli.yaml`

Command:

```bash
uv run --extra dev axiom-corpus-ingest extract-belgian-eli \
  --base data/corpus \
  --version 2026-06-30-be-tax-benefit \
  --manifest manifests/be-tax-benefit-eli.yaml \
  --request-timeout 45
```

Result:

| Jurisdiction | Document class | Source files | Provisions | Coverage |
|---|---:|---:|---:|---:|
| `be` | `statute` | 6 | 248 | complete |
| `be` | `regulation` | 5 | 579 | complete |
| `be-bru` | `statute` | 3 | 613 | complete |
| `be-vlg` | `statute` | 2 | 670 | complete |
| `be-wal` | `statute` | 2 | 155 | complete |

Total provisions written: 2,265.

Notes:

- Sources are fetched from official ejustice ELI pages.
- `Justel` pages are used as consolidated article locators where available.
- Provision records mark `Justel` rows as `non_authentic_consolidated_locator`
  and include the corresponding `Moniteur`/`Staatsblad` ELI as
  `legal_authority_url`.
- The Justel income tax code page states that its consolidated update has been
  suspended since 2002 and points users to FisconetPlus for later amendments.
- The manifest now includes VAT Royal Decree No. 20
  (`eli/arrete/1970/07/20/1970072012`) as the upstream VAT-rate legal locator.
- The manifest now includes official article-body snapshots for the Flemish
  Groeipakket decree (`numac=2018040369`) and the Walloon family-benefits
  decree (`numac=2018201006`), while keeping Justel URLs as consolidated
  locators only.
