# 2026-07-03 Maine TANF Primary Sources

## Scope

Adds source-first corpus coverage for Maine TANF before RuleSpec encoding for
PolicyEngine parity.

The upstream source hierarchy for the current Maine TANF calculation is:

- Maine Revised Statutes Title 22, section 3762, from the official Maine
  Legislature/Revisor page. This statute defines the assistance-standards
  framework, income disregards, resource treatment, child support disregard,
  child care deduction, and benefit-calculation authority.
- 10-144 C.M.R. Chapter 331, Maine Public Assistance Manual for TANF, from the
  official Maine Secretary of State rules publication. This regulation/manual
  contains the operational TANF eligibility, budgeting, standard-of-need, and
  basic maximum grant tables. The current official DOCX is filing 2025-231,
  effective 2025-11-30.

The official Secretary of State Chapter 331 DOCX is a better source for the
grant tables than PolicyEngine's Cornell mirror reference. The narrower Maine
DHHS TANF 121A PDF remains useful corroboration for the 2024 table update, but
is not the most complete current source.

## Commands

```bash
uv run --project . axiom-corpus extract-official-documents \
  --base data/corpus \
  --version 2026-07-03-me-tanf-statute \
  --manifest manifests/us-me-tanf-statute-official-documents.yaml \
  --source-as-of 2026-07-03 \
  --expression-date 2026-07-03
```

```bash
uv run --project . axiom-corpus extract-official-documents \
  --base data/corpus \
  --version 2026-07-03-me-tanf-regulation \
  --manifest manifests/us-me-tanf-regulation-official-documents.yaml \
  --source-as-of 2026-07-03 \
  --expression-date 2025-11-30
```

## Result

- Maine Revised Statutes Title 22, section 3762 (`us-me` / `statute`)
  - Version: `2026-07-03-me-tanf-statute`
  - Source files: 1
  - Provisions written: 2
  - Coverage: complete
- Maine Chapter 331 Public Assistance Manual (`us-me` / `regulation`)
  - Version: `2026-07-03-me-tanf-regulation`
  - Source files: 1
  - Provisions written: 5
  - Coverage: complete

The Chapter 331 extraction captures the full public assistance manual, including
the appendix standard-of-need and basic maximum grant tables for FFY 2025 and
FFY 2026. The document is currently segmented into a small number of large
blocks because the DOCX relies on styled headings rather than stable legal
section labels throughout; no corpus rows were hand-written.

## Validation

```bash
AXIOM_CORPUS_INGEST_PUBLIC_KEY=... \
  uv run --project . axiom-corpus guard-ingested --base-ref origin/main --json
```

```bash
uv run --extra dev --project . python -m pytest -q tests/test_corpus_documents.py
```
