# Belgium LGAF and Brussels Social-Housing Ingest

Run date: 2026-07-03

Manifest:

- `manifests/be-lgaf-bru-social-housing-official-documents.yaml`

Command:

```bash
uv run --extra dev axiom-corpus-ingest extract-belgian-eli \
  --base data/corpus \
  --version 2026-07-03-be-lgaf-bru-social-housing \
  --manifest manifests/be-lgaf-bru-social-housing-official-documents.yaml \
  --source-as-of 2026-07-03 \
  --request-timeout 45
```

Scope:

- Federal LGAF family-allowance statute of 19 December 1939, using Justel as
  the consolidated article locator and Moniteur as the legal authority.
- Brussels-Capital Region Government order of 26 September 1996 organizing
  rental of social-housing dwellings, using Justel as the consolidated article
  locator and Moniteur as the legal authority.

Notes:

- This fills upstream legal-source gaps surfaced by structural validation of
  the Belgium RuleSpec family-benefits and Brussels social-housing modules.
- Provision rows retain Moniteur legal-authority metadata while the Justel
  source rows are marked as non-authentic consolidated locators.
