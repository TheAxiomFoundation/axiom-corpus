# Colorado SSI state supplement CCR ingestion

## Scope

- Source: Colorado Code of Regulations, 9 CCR 2503-5, Adult Financial Programs.
- Target program: Aid to the Needy Disabled - Colorado Supplement (AND-CS), also modeled in PolicyEngine as `co_state_supplement`.
- Source as of: 2026-06-20.
- Expression date: 2026-06-20.
- Corpus version: `2026-06-20-co-ssp-9-ccr-2503-5`.

## Command

```bash
uv run axiom-corpus-ingest extract-colorado-ccr --base data/corpus --version 2026-06-20-co-ssp --only-series "9 CCR 2503-5" --source-as-of 2026-06-20 --expression-date 2026-06-20 --workers 1 --download-dir /tmp/axiom-co-ssp-download
```

## Notes

- The extraction targeted the official Colorado Secretary of State CCR listing and associated PDF for 9 CCR 2503-5.
- The run completed with full coverage for the selected series.
- Generated artifacts contain 92 provision records from 90 parsed sections, with zero missing provisions and zero extractor errors.
- The source archive contains the CCR welcome and department listing HTML pages, the rule information HTML page, and the 9 CCR 2503-5 PDF.
- Section 3.546 covers the AND-CS Program and is present in the provision set for downstream RuleSpec encoding.

## Checks

Result: full coverage; 92 provision records, 0 missing, 0 errors.
