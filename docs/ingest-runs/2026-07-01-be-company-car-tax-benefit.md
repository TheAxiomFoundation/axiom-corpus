# 2026-07-01 Belgian Company-Car Benefit Corpus

## Scope

Snapshots official Belgian company-car benefit-in-kind sources for the federal
personal-income-tax formula:

- CIR 1992 article 36 is already available in the income-tax corpus at
  `be/statute/fisconetplus/cir92/revenus-2025/page-95` and
  `be/statute/fisconetplus/cir92/revenus-2025/page-96`.
- Moniteur ELI publication of the Royal Decree of 17 December 2025 setting
  2026 reference CO2 emissions for company-car benefits in kind.
- SPF Finances 2026 company-car FAQ explaining the current formula, indexed
  minimum annual benefit, beneficiary contribution, missing-CO2 fallbacks, and
  worked examples.

## Commands

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-01-be-company-car-tax-benefit-regulation \
  --manifest manifests/be-company-car-tax-benefit-official-documents.yaml

uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-01-be-company-car-tax-benefit-guidance \
  --manifest manifests/be-company-car-tax-benefit-guidance-documents.yaml
```

## Result

- Regulation jurisdiction/document class: `be` / `regulation`
- Regulation source files: 1
- Regulation provisions written: 2
- Regulation coverage: complete
- Guidance jurisdiction/document class: `be` / `guidance`
- Guidance source files: 1
- Guidance provisions written: 34
- Guidance coverage: complete

The Moniteur ELI page is fetched through its linked CGI article endpoint
because the clean ELI route returns HTTP 404 in the extractor. The manifest
keeps the ELI URL as the legal authority and citation target.
