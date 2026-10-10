# North Carolina TY2026 Income-Tax Statute Core

## Scope

This local successor scope contains the four North Carolina General Statutes
needed for a resident individual income-tax calculation:

- G.S. 105-153.5, modifications to adjusted gross income.
- G.S. 105-153.7, the individual income-tax rate.
- G.S. 105-153.9, the credit for income taxes paid to another jurisdiction.
- G.S. 105-153.11, the credit for certain real-property donations.

The retained Chapter 105 consolidation predates the July 2026 amendments. The
builder therefore applies the enacted text from S.L. 2026-11 §24(a)-(b),
S.L. 2026-31 §1.5(b) and §1.8, and S.L. 2026-41 §44.1 and §44.2. Section 1.8
is included because it expressly applies to taxable years beginning on or
after January 1, 2026, even though it was not part of the original overlay
list.

G.S. 105-153.9 has two official renditions in the retained source. The
splitter selects the rendition effective for taxable years beginning on or
after January 1, 2023 for TY2026. It records the heading and body hash of both
renditions in provision metadata, and the unchanged source snapshot preserves
the complete text and provenance of both.

## Build

```bash
uv run --extra dev python -m scripts.build_nc_ty2026_statutes \
  --base data/corpus \
  --manifest manifests/us-nc-ty2026-income-tax-core.yaml
```

The builder verifies the exact SHA-256 of all four retained official NC
legislative sources, applies only audited prior-text replacements, and fails
if the expected text or temporal rendition is missing or ambiguous.

## Boundary

The scope is a local statute prerequisite. It is not published, loaded,
released, or production-selected. No final 2026 D-400 was available, so no
form content was fabricated and final liability remains explicitly deferred.
