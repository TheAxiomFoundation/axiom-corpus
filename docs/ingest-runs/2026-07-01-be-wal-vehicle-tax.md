# 2026-07-01 Walloon Vehicle-Tax Corpus

## Scope

Snapshots upstream Walloon tax-on-entry-into-service sources before encoding
current passenger-car TMC rules:

- Moniteur ELI for the 7 September 2023 decree replacing the Code des taxes
  assimilees article 98 TMC formula, effective 1 July 2025.
- Wallex current locator for the Code des taxes assimilees Walloon vehicle-tax
  competence and modification history.
- Moniteur ELI for the 30 May 2025 decree adapting the TMC formula, electric
  coefficients, family reductions, and default vehicle-characteristic rules.
- SPW Finances indexed passenger-car TMC parameter page valid from 1 July 2026
  through 30 June 2027.
- SPW Finances indexed annual circulation-tax PDF valid from 1 July 2026
  through 30 June 2027.

## Command

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-01-be-wal-vehicle-tax \
  --manifest manifests/be-wal-vehicle-tax-official-documents.yaml
```

## Result

- Jurisdiction: `be-wal`
- Document class: `statute`
- Source files: 5
- Provisions written: 10
- Coverage: complete
- Coverage path:
  `data/corpus/coverage/be-wal/statute/2026-07-01-be-wal-vehicle-tax.json`

The Moniteur ELI pages are fetched through their linked CGI article endpoints
because the clean ELI route returns a complete article body with HTTP 404.
The manifest keeps the ELI URL as the legal authority and source citation.
