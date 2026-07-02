# 2026-07-02 Brussels BE HOME Property-Tax Premium Corpus

## Scope

Snapshots official Brussels-Capital BE HOME premium legal sources from
Belgian ELI / Justel with Moniteur links retained as the publication authority.

Included provisions:

- 23 November 2017 Brussels ordinance, Articles 13-17: definitions,
  household eligibility, recipient rule, 1 January situation date, withdrawal,
  repayment, and fraud penalty rules for the BE HOME premium.
- 30 April 2020 Brussels ordinance, Articles 2-3: replacement of Article 14,
  paragraph 1 with the 130 EUR base amount, CPI coefficient, euro-rounding
  rule, and first application date.

The 12 December 2016 second tax-reform chapter is historical for current
calculation purposes: Article 17 of the 2017 ordinance abrogates it except for
premiums granted based on the 1 January 2016 or 1 January 2017 situations.

## Command

```bash
uv run --extra dev axiom-corpus-ingest extract-belgian-eli \
  --base data/corpus \
  --version 2026-07-02-be-bru-be-home-property-tax-premium \
  --manifest manifests/be-bru-be-home-property-tax-premium-official-documents.yaml \
  --request-timeout 45
```

## Result

- Jurisdiction: `be-bru`
- Document class: `statute`
- Source files: 2
- Provisions written: 21
- Coverage: complete
- Coverage path:
  `data/corpus/coverage/be-bru/statute/2026-07-02-be-bru-be-home-property-tax-premium.json`

The extractor wrote generated corpus artifacts under `data/corpus/`:

- `data/corpus/inventory/be-bru/statute/2026-07-02-be-bru-be-home-property-tax-premium.json`
- `data/corpus/provisions/be-bru/statute/2026-07-02-be-bru-be-home-property-tax-premium.jsonl`
- `data/corpus/sources/be-bru/statute/2026-07-02-be-bru-be-home-property-tax-premium/`
