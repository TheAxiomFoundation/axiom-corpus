# 7 CFR Part 275 eCFR ingestion

## Scope

- Source: eCFR title 7 part 275, Performance Reporting System.
- Source as of: 2026-06-12.
- Expression date: 2026-06-12.
- Corpus version: `2026-06-15-title-7-part-275`.

## Command

```bash
uv run axiom-corpus-ingest extract-ecfr --base data/corpus --version 2026-06-15 --as-of 2026-06-12 --expression-date 2026-06-12 --only-title 7 --only-part 275 --workers 1
```

## Notes

- Initial scoped extraction completed with full coverage, but inspection showed eCFR table rows were present in the source XML and absent from provision bodies.
- The eCFR corpus extractor was updated to preserve table rows as ordered block text before regenerating this scope.
- Regenerated artifacts contain 32 inventory items and 32 provision records with complete coverage.
- Spot checks confirmed formula rows in sections 275.3 and 275.11, including `n′ = .011634 N + 33.66` and `n = 300 + [0.042(N−10,000)]`.

## Checks

```bash
uv run --extra dev python -m pytest tests/test_corpus_ecfr.py -q
```

Result: 10 passed.
