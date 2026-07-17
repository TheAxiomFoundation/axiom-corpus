# Montana SNAP policy manual corpus ingest

## Official source boundary

The Montana Department of Public Health and Human Services publishes the SNAP policy
manual as separate PDFs on its official manual index. On July 17, 2026, the index linked
82 unique policy PDFs. The retained July table of contents lists exactly those 82 sections
plus section 1704-1, Nutrition Education Programs. Although the HTML index omits 1704-1,
the corresponding official DPHHS PDF remains live and its internal latest revision date is
July 11, 2024. This scope therefore retains all 83 sections asserted by the current table
of contents and records whether each was discovered through the HTML index or the TOC.

The manual covers application processing, household composition, nonfinancial
requirements, resources, income, deductions, work registration, E&T, ABAWD policy,
issuance, case management, hearings, quality control, tribal offices, E&T operators, and
nutrition education. Each document records the effective date displayed by the official
index, or the latest internal revision for TOC-only section 1704-1, and pins the retained
PDF's SHA-256 digest.

Montana's food-restriction demonstration does not begin until September 30, 2026. Its
future-effective materials are not mixed into this current-effective July 17 manual scope.

## Generated scope

No corpus row is written by hand. The standard manifest-driven extractor retains all 83
official PDFs and generates one source root plus one row for each of their 352 pages:

```bash
env -u UV_FROZEN uv run --extra dev axiom-corpus extract-official-documents \
  --base data/corpus \
  --version 2026-07-17-mt-snap-policy-manual \
  --manifest manifests/us-mt-snap-manual.yaml
```

The superseded `2026-05-27-mt-snap-manual` scope contains 429 derived rows but retains
none of its 82 referenced source files. It is removed only after this source-backed
replacement is committed and signed.
