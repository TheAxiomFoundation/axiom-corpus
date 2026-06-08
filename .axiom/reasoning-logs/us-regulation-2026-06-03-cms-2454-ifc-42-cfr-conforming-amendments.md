CMS-2454-IFC CFR section slice ingest

Source:
- Federal Register document: 2026-11094
- Citation: 91 FR 33348
- Publication date: 2026-06-03
- Effective date: 2026-07-31
- Corpus source text: data/corpus/sources/us/rulemaking/2026-06-03-cms-2454-ifc-types-rule-term-cms-2454-ifc-limit-1/federal-register/documents/2026-11094.txt

Scope:
- 42 CFR 431.213
- 42 CFR 431.231
- 42 CFR 438.58
- 42 CFR 457.340
- 42 CFR 457.344
- 42 CFR 457.960
- 42 CFR 600.320

Command:

```bash
uv run --extra dev axiom-corpus-ingest extract-federal-register-cfr-sections \
  --base data/corpus \
  --version 2026-06-03-cms-2454-ifc-42-cfr-conforming-amendments \
  --source-text data/corpus/sources/us/rulemaking/2026-06-03-cms-2454-ifc-types-rule-term-cms-2454-ifc-limit-1/federal-register/documents/2026-11094.txt \
  --section '42 CFR 431.213' \
  --section '42 CFR 431.231' \
  --section '42 CFR 438.58' \
  --section '42 CFR 457.340' \
  --section '42 CFR 457.344' \
  --section '42 CFR 457.960' \
  --section '42 CFR 600.320' \
  --document-number 2026-11094 \
  --document-citation '91 FR 33348' \
  --document-title 'Medicaid Program; Community Engagement Requirement for Certain Individuals' \
  --document-type interim_final_rule_with_comment_period \
  --source-url 'https://www.federalregister.gov/documents/2026/06/03/2026-11094/medicaid-program-community-engagement-requirement-for-certain-individuals' \
  --source-as-of 2026-06-03 \
  --expression-date 2026-07-31 \
  --source-document-citation-path us/rulemaking/federal-register/2026-06-03/2026-11094
```

Extraction notes:
- The extractor uses explicit requested CFR section references.
- The generated scope includes CFR part container records for parent integrity.
- Section bodies start at the Federal Register `Sec.` heading.
- Section bodies stop at the next amendatory instruction, next part heading, document signature, or next blank-line-delimited `Sec.` heading.
- Same-section removal instructions, such as `Section 457.344 is removed`, are retained in the removed section body.
- Wrapped cross-references such as `Sec. 457.350` are retained as body text, not treated as headings.

Validation:
- `uv run --extra dev python -m pytest tests/test_corpus_federal_register.py -q`
- `uv run --extra dev axiom-corpus-ingest extract-federal-register-cfr-sections ...`
- Output coverage: complete, source_count 11, provision_count 11, matched_count 11.
