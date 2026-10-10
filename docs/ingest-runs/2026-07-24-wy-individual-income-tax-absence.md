# Wyoming individual income-tax absence authority (2026-07-24)

This scope preserves two current official Wyoming sources. The State of
Wyoming portal affirmatively states that Wyoming does not possess an
individual or corporate income tax. The page reports an October 16, 2025
update and displays a 2026 State of Wyoming copyright. The Wyoming Legislative
Service Office's May 2026 short report separately states that Wyoming does not
have a state income tax.

Together these sources support the tax-year-2026 full-year-resident individual
income-tax result through the pre-credit tax stage. The source-backed zero is
the legal absence of a state individual income tax, not a zero-income
assumption or fictional zero-percent bracket.

Neither source certifies a complete tax-year-2026 nonrefundable-credit or
refundable-credit inventory, credit ordering, or signed net-liability surface.
Those downstream stages must remain explicitly source held rather than being
inferred from the no-individual-income-tax statements.

Business and entity taxes, payments, filing administration, local taxes, and
nonresident allocation are outside this scope.

Artifacts are generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-24-wy-individual-income-tax-absence \
  --manifest manifests/us-wy-2026-individual-income-tax-absence.yaml
```

The archived sources are the complete current state-portal HTML page and the
complete official LSO PDF. Normalization restricts the LSO provision to page
22, where the operative no-state-income-tax statement appears.
