# 2026-07-01 Flemish Fiscal Code Article-Version Corpus

## Scope

Snapshots current Vlaamse Codex Fiscaliteit article-version JSON through the
official Codex Vlaanderen frontend proxy after identifying the original
Moniteur/ELI publication for the Decree of 13 December 2013.

Included provisions:

- Article 2.7.4.1.1: Flemish inheritance-tax rate table.
- Article 2.8.4.1.1: Flemish gift-tax rate table.
- Article 2.1.4.0.1: Flemish immovable-withholding-tax rates.
- Article 2.1.4.0.1 comment: Moniteur indexation notices attached by Vlaamse
  Codex, including assessment year 2026 rates.
- Article 2.1.5.0.1: Flemish immovable-withholding-tax reductions.
- Article 2.2.4.0.1: Flemish circulation-tax rates.
- Article 2.2.4.0.4: Flemish additional LPG circulation tax.
- Article 2.2.4.0.5: Flemish municipal decime on circulation tax.
- Article 2.3.4.1.1: Flemish BIV vehicle scope and electric/hydrogen amount.
- Article 2.3.4.1.2/1: Flemish post-2020 BIV formula.
- Article 2.3.4.1.3: Flemish BIV minimum and maximum.
- Article 2.3.5.0.1: Flemish natural-gas BIV reduction.

## Command

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-01-be-vlg-fiscal-code \
  --manifest manifests/be-vlg-fiscal-code-official-documents.yaml
```

## Result

- Jurisdiction: `be-vlg`
- Document class: `statute`
- Source files: 12
- Provisions written: 24
- Coverage: complete
- Coverage path:
  `data/corpus/coverage/be-vlg/statute/2026-07-01-be-vlg-fiscal-code.json`

The JSON article bodies use `json_html_as_single_block` so Codex HTML
fragments with leading text before a paragraph are preserved in the generated
provision block.
