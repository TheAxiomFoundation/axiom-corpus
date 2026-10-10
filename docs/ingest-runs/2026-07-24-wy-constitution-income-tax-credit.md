# Wyoming constitutional income-tax credit boundary (2026-07-24)

This scope preserves article 15, section 18 of the current official Wyoming
Constitution. The section requires any tax imposed on income to allow a full
credit for sales, use, and ad valorem taxes paid in the taxable year by the
same taxpayer to a Wyoming taxing authority.

The section is a higher-authority boundary check for the current official
sources that state Wyoming has no individual or state income tax. It does not
itself impose an income tax, and it does not prove a complete nonrefundable-
credit, refundable-credit, credit-ordering, or signed net-liability surface.
Those downstream stages remain explicitly source held.

The artifact is generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-24-wy-constitution-income-tax-credit \
  --manifest manifests/us-wy-2026-constitution-income-tax-credit.yaml
```

The archived source is the complete official Wyoming Legislature HTML page
for constitution article 15. Normalization selects only the heading and
operative text of section 18.
