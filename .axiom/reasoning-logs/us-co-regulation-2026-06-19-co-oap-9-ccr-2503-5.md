# Colorado OAP CCR ingestion

## Scope

- Source: Colorado Code of Regulations, 9 CCR 2503-5, Adult Financial Programs.
- Source as of: 2026-06-19.
- Expression date: 2026-06-19.
- Corpus version: `2026-06-19-co-oap-9-ccr-2503-5`.

## Command

```bash
uv run axiom-corpus-ingest extract-colorado-ccr --base data/corpus --version 2026-06-19-co-oap --only-series "9 CCR 2503-5" --source-as-of 2026-06-19 --expression-date 2026-06-19 --workers 1 --download-dir /tmp/axiom-co-oap-download
```

## Notes

- The extraction targeted the official Colorado Secretary of State CCR listing and associated PDF for 9 CCR 2503-5.
- The run completed with full coverage for the selected series.
- Generated artifacts contain 92 provision records from 90 parsed sections, with zero missing provisions and zero extractor errors.
- The source archive contains the CCR welcome and department listing HTML pages, the rule information HTML page, and the 9 CCR 2503-5 PDF.

## Checks

```bash
uv run axiom-corpus-ingest extract-colorado-ccr --base data/corpus --version 2026-06-19-co-oap --only-series "9 CCR 2503-5" --source-as-of 2026-06-19 --expression-date 2026-06-19 --workers 1 --download-dir /tmp/axiom-co-oap-download
```

Result: full coverage; 92 provision records, 0 missing, 0 errors.
