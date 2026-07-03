# Belgium Guaranteed-Family and Brussels Support Ingest

Run date: 2026-07-03

Manifest:

- `manifests/be-guaranteed-family-bru-support-official-documents.yaml`

Command:

```bash
uv run --extra dev axiom-corpus-ingest extract-belgian-eli \
  --base data/corpus \
  --version 2026-07-03-be-guaranteed-family-bru-support \
  --manifest manifests/be-guaranteed-family-bru-support-official-documents.yaml \
  --source-as-of 2026-07-03 \
  --request-timeout 45
```

Scope:

- Federal royal decree of 25 October 1971 implementing the guaranteed-family-benefits law.
- Brussels BE HOME ordinances of 23 November 2017 and 30 April 2020.
- Brussels Common Community Commission elderly-care allowance ordinance and implementing orders.
- Brussels rent allowance and relocation accompaniment allowance orders.

Notes:

- This fills official upstream ELI sources missing from RuleSpec structural validation of guaranteed family benefits, Brussels BE HOME, Brussels elderly-care allowance, and Brussels housing support modules.
- Provision rows retain Moniteur legal-authority metadata while the Justel source rows are marked as non-authentic consolidated locators.
