# Connecticut 2026 Supplement Section 12-704e

This scope preserves the Connecticut General Assembly's official consolidated
2026 Supplement text for General Statutes Section 12-704e, the resident earned
income tax credit.

The retained section supplies:

- the 40 percent applicable percentage for taxable years beginning on or after
  January 1, 2023;
- refundable-excess treatment;
- the additional $250 credit for an otherwise eligible taxpayer with at least
  one qualifying child for federal income tax purposes;
- the separate-state-return allocation rule; and
- the amendment history recording that P.A. 25-168, Section 371, applies to
  taxable years beginning on or after January 1, 2025.

The official Connecticut page does not present a TLS certificate chain accepted
by the repository's Python trust store, so the manifest records
`verify_tls: false`. The HTTPS URL, complete downloaded HTML, and generated
artifact hashes remain preserved for review and deterministic verification.

The generic official-document adapter retains the complete Chapter 229
Supplement HTML and emits a structural document root plus one body-bearing
section:

- `us-ct/statute/2026-supplement/12-704e`
- `us-ct/statute/2026-supplement/12-704e/earned-income-tax-credit`

The retained HTML has SHA-256
`2faa8eebcad4e951d01bfd563941ba74e4f8d7d2b0d29a84a631cf19f8752511`.
Coverage is complete at two inventory citations and two normalized provisions,
with no missing, extra, or duplicate citations.

Artifacts are generated without publication or database loading:

```bash
axiom_with_corpus_ingest_key uv run --extra dev axiom-corpus-ingest \
  extract-official-documents \
  --base data/corpus \
  --version 2026-07-24-ct-income-tax-supplement \
  --manifest manifests/us-ct-2026-supplement-section-12-704e.yaml
```

The protected wrapper supplies signing material only to the ingest process.
Private signing material is neither printed nor stored in the repository.
Release selection, publication, database loading, and RuleSpec changes remain
separate reviewed steps.
