# Tennessee individual income-tax zero-liability authority (2026-07-24)

This scope preserves the enacted and current official authorities that control
the tax-year-2026 full-year-resident individual income-tax pipeline in
Tennessee.

Section 13 of 2017 Public Chapter 181 amended Tennessee Code Annotated section
67-2-102 to set the Hall income-tax rate to zero percent for every tax year
beginning on or after January 1, 2021. Sections 14 and 15 made the related
cross-reference and sunset changes.

Current Tennessee Department of Revenue guidance confirms the complete
natural-person boundary. The Hall tax applied only to individuals and other
entities receiving interest from bonds and notes and dividends from stock; it
was repealed for periods beginning January 1, 2021 or later, and Revenue
instructs taxpayers not to file a return for any tax year beginning on or after
that date. Revenue's current GEN-34 guidance separately states that Tennessee
has no state income tax on earned income and no income-tax withholding
requirement.

Together, the enacted permanent zero rate and the current no-return and
no-earned-income-tax guidance establish an input-independent zero annual
resident individual income-tax result for tax year 2026. There is no operative
resident individual deduction, exemption, surtax, nonrefundable-credit, or
refundable-credit return stage after repeal; liability is zero before credits,
after credits, and before payments. This conclusion concerns the annual state
individual income-tax return and does not treat the absence of withholding as a
payment computation.

The scope excludes franchise and excise taxes, business and entity taxes,
historic Hall-tax periods, payments and withholding administration, local
taxes, and nonresident or part-year allocation.

Artifacts are generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-24-tn-hall-income-tax-zero-rate-statute \
  --manifest manifests/us-tn-2017-public-chapter-181-hall-income-tax-zero-rate.yaml

uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-24-tn-individual-income-tax-zero-liability-guidance \
  --manifest manifests/us-tn-2026-individual-income-tax-zero-liability-guidance.yaml
```

The Public Chapter extractor retains PDF pages 3–4 beginning at section 13.
Because sections 16–18 continue on the same second page, their unrelated
fuel-tax text remains in the normalized page window for source fidelity but is
outside the certified individual-income-tax scope. The Hall-tax webpage
extractor retains only its main Revenue content, and the GEN-34 extractor
retains the official API article body rather than site navigation.
