# South Carolina 2026 Act No. 110 overlay repair

The retained official South Carolina Legislative Services Agency sources already
included both the Title 12, Chapter 6 Code HTML and
[2026 Act No. 110 (H.4216)](https://www.scstatehouse.gov/sess126_2025-2026/bills/4216.htm).
The original extraction applied only Act 110 SECTION 1 to the rate schedule in
Section 12-6-510. This source-first repair applies the same enacted act to all
four affected normalized sections:

- SECTION 1 replaces Section 12-6-510(C);
- SECTION 2 adds Section 12-6-50(21), which does not adopt Internal Revenue
  Code Section 63(b) through (g);
- SECTION 3 adds Section 12-6-1140(15), the South Carolina Income Adjusted
  Deduction; and
- SECTION 7 replaces Section 12-6-3632 with the earned income tax credit capped
  at two hundred dollars.

Each overlaid provision retains both the codified-base and operative-session-law
components in metadata and records the applicable Act 110 section in its source
history. The source snapshot was unchanged: the Act HTML SHA-256 remains
`9e3fbbd48551b138866bd5c54f1faadd6404d624ba350195459c0c65477e7493`.

Because the earlier scope was selected by published releases, it remains
byte-for-byte unchanged. Deterministic regeneration creates the self-contained
successor scope
`2026-07-24-sc-act110-us-sc-title-12-chapter-6`, with complete coverage at 158
inventory citations and 158 normalized provisions and no missing, extra, or
duplicate citations. Codified Section 12-6-520 is intentionally excluded
because it is already supplied by the separate South Carolina recovery scope;
the successor release is therefore collision-free.

The `us-rulespec-2026-07-24-sc-act110-current` selector succeeds
`us-rulespec-2026-07-24-cms-435-correction-immutable-scopes` and replaces only
the prior South Carolina Chapter 6 scope. The selector retains 198 unique
scopes and passes deep release validation with no errors.

Artifacts are regenerated without publication or database loading:

```bash
axiom_with_corpus_ingest_key uv run --extra dev axiom-corpus-ingest \
  extract-state-statutes \
  --base data/corpus \
  --manifest manifests/state-income-tax-recovery.yaml \
  --only-source-id us-sc-code
```

The protected wrapper supplies signing material only to the ingest process.
Private signing material is neither printed nor stored in the repository.
Release selection, publication, database loading, and RuleSpec changes remain
separate reviewed steps.
