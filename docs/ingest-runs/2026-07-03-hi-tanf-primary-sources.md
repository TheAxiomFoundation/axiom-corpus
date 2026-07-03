# 2026-07-03 Hawaii TANF Primary Sources

## Scope

Adds source-first corpus coverage for Hawaii TANF before RuleSpec encoding:

- Hawaii Revised Statutes Chapter 346 from the official Hawaii State Legislature current HRS mirror.
- Hawaii Administrative Rules Chapters 17-656.1, 17-676, and 17-678 from official Hawaii Department of Human Services PDFs.

The statute source is the upstream authority layer. The administrative rules contain the TANF eligibility, income, standard-of-need, standard-of-assistance, and monthly-assistance-allowance details needed for PolicyEngine parity work. The current HAR 17-678 PDF is image-only, so the ingestion uses the manifest-controlled OCR path rather than manual corpus rows.

## Commands

```bash
uv run --extra dev axiom-corpus-ingest extract-state-statutes \
  --base data/corpus \
  --manifest manifests/us-hi-hrs-chapter-346.yaml
```

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-03-hi-tanf-admin-rules \
  --manifest manifests/us-hi-tanf-admin-rules.yaml
```

## Result

- Hawaii Revised Statutes Chapter 346 (`us-hi` / `statute`)
  - Version: `2026-07-03-hi-hrs-us-hi-chapter-346`
  - Source files: 282
  - Provisions written: 280
  - Coverage: complete
- Hawaii Administrative Rules Chapters 17-656.1, 17-676, and 17-678 (`us-hi` / `regulation`)
  - Version: `2026-07-03-hi-tanf-admin-rules`
  - Source files: 3
  - Provisions written: 124
  - Coverage: complete

The HAR 17-678 extraction confirms the current TANF monthly assistance allowance is sixty-two per cent of the standard of need. HAR 17-676-54.1 contains the TANF net-income calculation, including the twenty percent standard deduction, two hundred dollar flat deduction, and fifty-five percent adult-recipient earned income disregard for months one through twenty-four.
