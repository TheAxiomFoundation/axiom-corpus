# Michigan 2026 individual-income-tax rate notice (2026-07-21)

This scope preserves the Michigan Department of Treasury Bureau of Tax Policy's
official April 15, 2026 taxpayer notice determining the tax-year 2026 rate for
individuals and fiduciaries under MCL 206.51.

The notice states that Fiscal Year 2025 general fund/general purpose revenue
decreased by 1.56 percent while inflation increased by 2.70 percent. Treasury
therefore records that the conditions for applying the formulary reduction in
MCL 206.51(1)(c) were not met and that the Section 51 rate for tax year 2026 is
4.25 percent.

Artifacts are generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-21-mi-2026-income-tax-rate-notice \
  --manifest manifests/us-mi-2026-income-tax-rate-notice.yaml
```

The extraction selects only the notice body from the official Michigan.gov
page. It writes the canonical source snapshot, inventory, normalized provision,
and coverage artifacts under the `us-mi/guidance` scope. The successor release
selector remains unpublished.
