# Head Start 45 CFR part 1302 corpus ingest

Date: 2026-06-24

Purpose: support Axiom RuleSpec encoding and PolicyEngine parity review for active Head Start and Early Head Start eligibility.

Source: official eCFR Versioner API for title 45, part 1302. The requested current date 2026-06-24 was not served for title 45; eCFR reported the latest title issue date as 2026-06-22, so this ingest uses `as_of=2026-06-22` and records that date in source provenance.

Command:

```bash
axiom-corpus-ingest extract-ecfr \
  --base data/corpus \
  --version 2026-06-24 \
  --as-of 2026-06-22 \
  --expression-date 2026-06-22 \
  --only-title 45 \
  --only-part 1302 \
  --workers 2 \
  --allow-incomplete
```

Result: extracted title 45 part 1302 with complete coverage: 63 provisions written, 63 matched, 0 missing, and 0 extra provisions.
