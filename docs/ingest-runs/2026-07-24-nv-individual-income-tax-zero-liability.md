# Nevada natural-person income-tax zero-liability authority (2026-07-24)

This scope preserves the current official Nevada constitutional authority for
the annual resident personal-income-tax result of a natural person through the
pre-credit tax stage.

Article 10, section 1, subsection 9 of the Nevada Constitution prohibits an
income tax on the wages or personal income of natural persons. The same
subsection expressly permits taxes on the income or revenue of a business in
whatever form it is conducted for profit in Nevada. A separate normalized
record preserves the official section 1 amendment history: it records the
eleventh amendment's ratification at the May 2, 1989 special election, the last
approved amendment shown in 2002, and the failed 2014 proposal. Together with
the official current source snapshot dated 2026-07-24, that history grounds the
prohibition's tax-year-2026 applicability.

The resulting complete zero is limited to a natural person's resident
personal-income tax before credits. The constitutional text alone does not
establish the absence of refundable individual credits or a signed net
liability after such credits; those stages remain source held in RuleSpec. The
scope does not cover a business or entity tax, including a tax measured by
business income or revenue, and it does not cover payments, filing
administration, local taxes, or nonresident allocation.

Artifacts are generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-24-nv-individual-income-tax-zero-liability \
  --manifest manifests/us-nv-individual-income-tax-zero-liability.yaml
```

The selectors preserve the operative subsection 9 paragraph and section 1
amendment-history source note. Each archived source remains the complete
official Nevada Constitution HTML page.
