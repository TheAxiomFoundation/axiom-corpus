# Pennsylvania personal-income-tax rates (2026-07-21)

This scope preserves the Pennsylvania Department of Revenue's official
personal-income-tax rate table. The current row states that the rate for 2004
through the present is 3.07 percent, numerically grounding the current
Pennsylvania individual-income-tax rate of `0.0307`.

The page also includes the Department's historical rate rows from 1971 through
2003. The corpus extraction selects only that substantive rate table and does
not include the surrounding PA.gov navigation. Because the page does not state
a separate publication or effective date for the current web expression, the
scope uses the 2026-07-21 source observation date as its expression date while
retaining `2004-present` as the current rate period in source metadata.

Artifacts are generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-21-pa-personal-income-tax-rates \
  --manifest manifests/us-pa-personal-income-tax-rates.yaml
```

The run writes the canonical source snapshot, inventory, normalized provision,
and coverage artifacts under the `us-pa/guidance` scope. The unpublished
successor release selector `us-rulespec-2026-07-21-pa-pit-current` adds this
scope to `us-rulespec-2026-07-21-mi-pit-current` without changing its existing
scope membership.

Both the Michigan predecessor and Pennsylvania table use stable semantic child
paths (`rate-determination` and `rate-table`) instead of generated `/block-N`
identities. This scope therefore requires no citation-irregularity ratchet
increase and does not rewrite any existing released citation path.
