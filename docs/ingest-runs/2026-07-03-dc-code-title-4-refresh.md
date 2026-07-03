# DC Code Title 4 Refresh

## Scope

- Jurisdiction: `us-dc`
- Document class: `statute`
- Version: `2026-05-19-title-4`
- Source: official DC Code XML snapshot under `dc-law-xml/titles/4`
- Purpose: refresh the tracked Title 4 slice after the DC XML table parser fix so tabular section text, including D.C. Code § 4-205.52 TANF payment levels, is present in provision bodies.

## Command

```bash
uv run axiom-corpus-ingest extract-dc-code \
  --base data/corpus \
  --version 2026-05-19 \
  --source-dir /tmp/axiom-dc-statute-refresh-20260703/data/corpus/sources/us-dc/statute/2026-04-29/dc-law-xml/titles \
  --only-title 4 \
  --source-as-of 2025-12-23 \
  --expression-date 2025-12-23
```

## Result

- `title_count`: 1
- `container_count`: 99
- `section_count`: 633
- `provisions_written`: 732
- `source_file_count`: 634
- `coverage_complete`: true
- `missing_count`: 0
- `extra_count`: 0

The refreshed `us-dc/statute/4/4-205.52` body includes the table headers `Family Size`, `Standard Payment Level`, and `Level of Assistance` plus the statutory TANF payment rows.

No R2 sync, Supabase load, publication, or production row deletion was performed in this run.
