# Delaware Code Title 31 Chapter 5

This run adds the upstream Delaware statutory authority for the Delaware SSI
state supplement parity surface.

## Scope

- Jurisdiction: `us-de`
- Document class: `statute`
- Version: `2026-07-04-us-de-title-31-chapter-5`
- Source: official Delaware Code HTML, Title 31, Chapter 5
- Source as of: `2026-06-18`
- Purpose: provide the Delaware statute layer above the already ingested DSSM
  13000 and SSA POMS sources for `de_ssp`.

## Command

```bash
uv run --with xlrd axiom-corpus-ingest extract-delaware-code \
  --base data/corpus \
  --version 2026-07-04 \
  --only-title 31 \
  --only-chapter 005 \
  --source-as-of 2026-06-18 \
  --expression-date 2026-06-18 \
  --workers 1
```

## Result

- `title_count`: 1
- `container_count`: 3
- `section_count`: 38
- `provisions_written`: 41
- `source_file_count`: 3
- `coverage_complete`: true
- `missing_count`: 0
- `extra_count`: 0

The generated records include 31 Del. C. § 505, which defines categories of
assistance, and 31 Del. C. § 512, which authorizes the Department of Health and
Social Services to administer the chapter and enter Title XVI Supplementary
Security Income agreements.
