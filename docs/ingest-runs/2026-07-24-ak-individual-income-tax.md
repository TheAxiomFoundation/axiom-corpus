# Alaska individual income-tax authority (2026-07-24)

This scope preserves the current official Alaska Statutes provisions that
control the tax-year-2026 full-year-resident individual income-tax pipeline.

AS 43.20.011 imposes the Alaska Net Income Tax Act tax on corporations.
AS 43.20.012(a)(1) more directly states that the tax imposed by the chapter
does not apply to an individual. This supports an input-independent zero
individual income-tax result through deductions, exemptions, taxable income,
tax, surtax, and nonrefundable-credit stages.

Alaska is not a complete-zero jurisdiction after that point. AS 43.20.012(b)
permits an individual to file a return for the credits in AS 43.20.013.
Section 43.20.013 provides an up-to-$100 resident credit for specified
political contributions and dues and a resident credit equal to 16 percent of
the federal household-and-dependent-care credit claimed. It directs the
commissioner to pay an allowed credit as a refund, but payment may not be made
without an appropriation.

The source does not establish a tax-year-2026 appropriation or current claim
mechanics. Refundable credits and signed net liability therefore remain
explicitly source held; their zero values are fail-closed sentinels, not
substantive zero-credit conclusions.

The 34th Legislature's HB 152, an individual-income-tax proposal that would
repeal AS 43.20.012(b) and AS 43.20.013, remained referred to House Finance as
of March 25, 2026 and is not treated as enacted authority.

The scope excludes corporate and pass-through-entity taxes, the Permanent Fund
Dividend, withholding and other payments, filing administration, local taxes,
and nonresident or part-year allocation.

Artifacts are generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-24-ak-individual-income-tax \
  --manifest manifests/us-ak-title-43-individual-income-tax-2026.yaml
```

The page window retains PDF pages 37–38, beginning at AS 43.20.011, and the
labeled-section extractor emits separate canonical provisions for
AS 43.20.011, AS 43.20.012, and AS 43.20.013.
