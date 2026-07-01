# Belgium Current Tax Document Ingest

Run date: 2026-06-30

Purpose:

- Snapshot current consolidated Belgian income-tax and VAT-rate documents needed
  after upstream ELI/Justel locators are identified.
- Preserve the distinction between legal authority and consolidation: Moniteur
  ELI/PDF remains the upstream legal locator, while FisconetPlus-derived text is
  used to extract current indexed parameters and current VAT-rate sections.

Income-tax command:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-06-30-be-income-tax-consolidated \
  --manifest manifests/be-income-tax-official-documents.yaml \
  --allow-incomplete
```

Income-tax result:

| Jurisdiction | Document class | Source files | Provisions | Coverage |
|---|---:|---:|---:|---:|
| `be` | `statute` | 1 | 744 | complete |

Key citation paths:

- `be/statute/fisconetplus/cir92/revenus-2025/page-181`
- `be/statute/fisconetplus/cir92/revenus-2025/page-182`
- `be/statute/fisconetplus/cir92/revenus-2025/page-461`

VAT command:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-06-30-be-vat-consolidated \
  --manifest manifests/be-vat-official-documents.yaml \
  --allow-incomplete
```

VAT result:

| Jurisdiction | Document class | Source files | Provisions | Coverage |
|---|---:|---:|---:|---:|
| `be` | `regulation` | 2 | 8 | complete |

Key citation paths:

- `be/regulation/moniteur/1970/07/31/1970072012`
- `be/regulation/fisconetplus/vat/royal-decree-20/Article 1`
- `be/regulation/fisconetplus/vat/royal-decree-20/TABLEAU A`
- `be/regulation/fisconetplus/vat/royal-decree-20/TABLEAU B`
- `be/regulation/fisconetplus/vat/royal-decree-20/TABLEAU C`

Notes:

- The original Moniteur PDF for AR No. 20 is image-only through the plain PDF
  extractor, but the source PDF is still snapshotted in corpus.
- The VAT consolidated PDF carries SPF Finances / FisconetPlus headers and
  MINFIN metadata; it is an administrative consolidation, not the legal source.

VAT Code exemption command:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-06-30-be-vat-code-consolidated \
  --manifest manifests/be-vat-code-official-documents.yaml
```

VAT Code exemption result:

| Jurisdiction | Document class | Source files | Provisions | Coverage |
|---|---:|---:|---:|---:|
| `be` | `statute` | 1 | 5 | complete |

VAT Code exemption citation paths:

- `be/statute/fisconetplus/vat-code/Article 41`
- `be/statute/fisconetplus/vat-code/Article 42`
- `be/statute/fisconetplus/vat-code/Article 43`
- `be/statute/fisconetplus/vat-code/Article 44`

VAT Code exemption notes:

- Article 41 supplies the maritime passenger and international air passenger
  transport exemptions used by the BEAMM VAT category map.
- Article 44 supplies the medical-services, education, real-estate rental, and
  insurance exemptions used by the BEAMM VAT category map.

Vehicle-tax Code locator command:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-06-30-be-vehicle-tax-code \
  --manifest manifests/be-vehicle-tax-code-official-documents.yaml \
  --allow-incomplete
```

Vehicle-tax Code locator result:

| Jurisdiction | Document class | Source files | Provisions | Coverage |
|---|---:|---:|---:|---:|
| `be` | `statute` | 1 | 3 | complete |

Brussels vehicle-tax guidance command:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-06-30-be-bru-vehicle-tax-guidance \
  --manifest manifests/be-bru-vehicle-tax-guidance-documents.yaml \
  --allow-incomplete
```

Brussels vehicle-tax guidance result:

| Jurisdiction | Document class | Source files | Provisions | Coverage |
|---|---:|---:|---:|---:|
| `be-bru` | `guidance` | 3 | 40 | complete |

Vehicle-tax citation paths:

- `be/statute/justel/code-taxes-assimilees/1965112350`
- `be-bru/guidance/brussels-fiscality/vehicle-tax/circulation-tax-2026/page-1`
- `be-bru/guidance/brussels-fiscality/vehicle-tax/circulation-tax-2026/page-5`
- `be-bru/guidance/brussels-fiscality/vehicle-tax/circulation-tax-2026/page-6`
- `be-bru/guidance/brussels-fiscality/vehicle-tax/circulation-tax-2026/page-7`
- `be-bru/guidance/brussels-fiscality/vehicle-tax/entry-into-service-tax-2026/page-1`
- `be-bru/guidance/brussels-fiscality/vehicle-tax/entry-into-service-tax-2026/page-4`
- `be-bru/guidance/brussels-fiscality/mytax/road-tax-tariffs-2025-2026/block-1`
- `be-bru/guidance/brussels-fiscality/mytax/road-tax-tariffs-2025-2026/block-6`
- `be-bru/guidance/brussels-fiscality/mytax/road-tax-tariffs-2025-2026/block-7`
- `be-bru/guidance/brussels-fiscality/mytax/road-tax-tariffs-2025-2026/block-14`
- `be-bru/guidance/brussels-fiscality/mytax/road-tax-tariffs-2025-2026/block-15`

Vehicle-tax notes:

- The Code des taxes assimilees aux impots sur les revenus is recorded as the
  upstream legal locator before using Brussels Fiscality rate guidance.
- The Brussels Fiscality PDFs are official current public guidance for index
  2026. They are not legal authority and should be cited with an upstream
  source check.
- The public TMC PDF gives minimum/maximum and fixed boat/aircraft amounts and
  refers detailed car and motorcycle rates to MyTax.
- The official MyTax HTML page is snapshotted as the third source file. It says
  the road-tax tariffs are valid from 1 July 2025 through 30 June 2026; block 1
  carries that validity statement, blocks 6 and 7 carry the motorcycle TMC
  non-leasing/leasing tables, and blocks 14 and 15 carry the ordinary car TMC
  non-leasing/leasing tables.

Excise command:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-06-30-be-excise-consolidated \
  --manifest manifests/be-excise-official-documents.yaml \
  --allow-incomplete
```

Excise result:

| Jurisdiction | Document class | Source files | Provisions | Coverage |
|---|---:|---:|---:|---:|
| `be` | `statute` | 3 | 10 | complete |

Excise citation paths:

- `be/statute/justel/excise/alcohol/1998003047/Article 5`
- `be/statute/justel/excise/alcohol/1998003047/Article 9`
- `be/statute/justel/excise/alcohol/1998003047/Article 12`
- `be/statute/justel/excise/alcohol/1998003047/Article 15`
- `be/statute/justel/excise/alcohol/1998003047/Article 17`
- `be/statute/justel/excise/tobacco/1997003241/Article 3`
- `be/statute/justel/excise/energy-products/2004021170/Article 419`

Excise notes:

- Moniteur ELI URLs are recorded as the upstream legal locators for the
  alcohol, tobacco, and energy-product statutes.
- Justel current consolidated HTML is used as the machine-readable rate text.
- The rate-bearing Justel articles are extracted with `anchor_range` sections
  to avoid broad page blocks swallowing or dropping statutory rate tables.
