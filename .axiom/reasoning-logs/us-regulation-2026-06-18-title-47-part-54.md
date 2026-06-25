# 47 CFR Part 54 eCFR Ingest

## Scope

Ingested 47 CFR part 54 for federal Lifeline parity work. The immediate RuleSpec targets are 47 CFR 54.403 and 54.409, but the eCFR extractor snapshots the full part so section, subpart, and sibling cross-references stay coherent.

## Source Date

The eCFR versioner API returned 404 for `2026-06-23` structure data. `titles.json` reported Title 47 as up to date as of `2026-06-18`, so this ingest uses `--as-of 2026-06-18`.

## Command

```bash
uv run axiom-corpus-ingest extract-ecfr --base data/corpus --version 2026-06-18 --as-of 2026-06-18 --only-title 47 --only-part 54 --workers 1
```

## Coverage

The extractor wrote 272 provision records and reported complete coverage with 272 matched source inventory items, 0 missing, and 0 extra.
