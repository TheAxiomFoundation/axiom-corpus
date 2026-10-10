# Ohio H.B. 96 final income-tax analysis (2026-07-21)

This scope preserves the Ohio Legislative Service Commission's official final
analysis of enacted Amended Substitute H.B. 96. The income-tax analysis states
the final tax-year-2026 schedule of $332 plus 2.75 percent of income above
$26,050 on page 456. Page 457 expressly identifies Section 757.120(A) and says
the act suspends annual inflation adjustments to the income-tax brackets and
personal exemptions for taxable years 2025 and 2026.

Artifacts are generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-21-oh-hb96-final-analysis \
  --manifest manifests/us-oh-hb96-final-analysis.yaml
```

The extraction snapshots the official PDF and normalizes its complete text as
one body-bearing child under a document root so the schedule and indexing-
suspension explanation remain in the same authoritative source context.
Publication and serving activation are separate, reviewed steps.
