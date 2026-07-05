# US OASDI Title II corpus ingest reasoning

Impact basis:

- rulespec-us issue 541 encodes the Social Security Title II benefit-formula
  chain (AIME, PIA, COLA application, retirement age, early-claiming
  reductions, delayed retirement credits) and cites 42 U.S.C. 402(q), 402(w),
  415(a), 415(b), 415(e), 415(i), and 416(l). None of those sections were in
  the corpus, so the encodings had no grounding target.

Official source:

- US Code Title 42 USLM XML from uscode.house.gov releasepoint Online@119-100
  (laws current through Public Law 119-100, 06/26/2026).
- Download URL: https://uscode.house.gov/download/releasepoints/us/pl/119/100/xml_usc42@119-100.zip
- USLM metadata: created 2026-04-17; publication Online@119-100.

Scope:

- Ingested the core OASDI benefit-computation sections of Title II instead of
  full Title 42, mirroring the SSI Title XVI (2026-06-20) and CHIP Title XXI
  (2026-06-26) scoped runs.
- Sections included: 42 U.S.C. 402, 403, 413, 414, 415, 416.
- This covers benefit entitlement and reductions/credits (402, including
  402(q) early-claiming reductions and 402(w) delayed retirement credits),
  family maximum and the earnings test (403), quarters of coverage (413),
  insured-status definitions (414), benefit computation including AIME, the
  90/32/15 PIA formula, bend-point indexing, and the COLA mechanism (415),
  and definitions including the section 416(l) retirement-age schedule.

Generated artifact:

- Command used the US Code ingester with repeated --section filters and
  --include-title; no corpus rows were written by hand.
- Because full Title 42 USLM XML is too large for normal GitHub review, the
  ingester wrote a generated scoped USLM source artifact containing only the
  selected sections while retaining the official download URL in inventory
  metadata.
- The US Code ingester emitted the Title 42 container, section rows,
  first-level subsection rows, and immediate paragraph rows from official USLM
  identifiers (1 title + 6 sections + 66 subsections + 204 paragraphs).
- Output run id: 2026-07-05-oasdi-title-ii-title-42.
- Coverage result: complete; 277 source inventory rows matched 277 provision
  rows.

Operative-text verification (grounding targets for rulespec-us issue 541):

- `us/statute/42/415/a/1` carries the 90 percent / 32 percent / 15 percent
  PIA formula percentages.
- `us/statute/42/415/i` carries the cost-of-living computation mechanism
  (base quarter, applicable increase percentage, Consumer Price Index) and
  the next-lower-multiple-of-$0.10 rounding.
- `us/statute/42/416/l` carries the full retirement-age schedule (65 to 67
  with the two-twelfths age increase factors).
- `us/statute/42/402/q` carries the early-claiming reduction fractions and
  the 36-month tier break; `us/statute/42/402/w` carries the increment-month
  delayed-retirement increase.

Command:

```bash
env -u UV_FROZEN uv run --extra dev axiom-corpus-ingest extract-usc \
  --base data/corpus \
  --version 2026-07-05-oasdi-title-ii \
  --source-xml ~/.axiom/uscode-119-100/usc42.xml \
  --title 42 \
  --section 402 --section 403 --section 413 --section 414 --section 415 --section 416 \
  --include-title \
  --source-as-of 2026-06-26 \
  --expression-date 2026-06-26 \
  --source-url "https://uscode.house.gov/download/releasepoints/us/pl/119/100/xml_usc42@119-100.zip"
```

Publication note:

- Supabase load-supabase and R2 sync-r2 are deliberately not run in this
  branch; the maintainer publication sequence in
  docs/agent-ingestion-runbook.md applies after merge.
