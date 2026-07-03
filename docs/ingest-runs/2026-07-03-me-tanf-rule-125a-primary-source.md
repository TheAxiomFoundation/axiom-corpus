# 2026-07-03 Maine TANF Rule 125A Primary Source

## Scope

Adds the official Maine DHHS adopted clean rule pages for TANF Rule 125A as a
supplemental primary source for the October 2025 TANF maximum-benefit and
standard-of-need chart update.

The broader Maine TANF ingest already includes the official Secretary of State
consolidated Chapter 331 DOCX. That consolidated DOCX is still the best source
for the full current manual. However, the DOCX has a malformed FFY 2026 table
cell for household size 5 with an adult included, rendering `$1,591` as
`15,91`. The DHHS adopted clean rule PDF for the same rulemaking preserves the
same chart with the ungarbled value. This run adds that adopted-rule source so
RuleSpec encoding can ground the numeric literal in an official source rather
than repairing the generated output by hand.

## Command

```bash
uv run --project . axiom-corpus extract-official-documents \
  --base data/corpus \
  --manifest manifests/us-me-tanf-rule-125a-official-documents.yaml \
  --version 2026-07-03-me-tanf-rule-125a
```

## Result

- Maine TANF Rule 125A maximum-benefit and standard-of-need chart (`us-me` /
  `regulation`)
  - Version: `2026-07-03-me-tanf-rule-125a`
  - Source files: 1
  - Provisions written: 2
  - Coverage: complete

The relevant table row is available at
`us-me/regulation/dhhs/ofi/chapter-331/tanf-rule-125a/maximum-benefit-and-standard-of-need`.
The extraction is intentionally limited to the adopted chart page so it can use
a stable chart citation suffix instead of page-number segmentation. No
generated corpus rows were hand-written.

## Validation

```bash
AXIOM_CORPUS_INGEST_PUBLIC_KEY=... \
  uv run --project . axiom-corpus guard-ingested --base-ref origin/main --json
```

```bash
uv run --extra dev --project . python scripts/validate_citation_paths.py --json
```
