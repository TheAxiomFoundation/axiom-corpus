# Colorado SNAP supporting policy refetch

## Source boundary

The current Colorado SNAP supporting scope retains exactly 13 official sources:
six live CDHS HTML pages, four current FFY/FY2026 CDHS PDFs, and the three FNS
food-restriction approval/modification PDFs that form the Healthy Choice decision
chain. The six CDHS pages were fetched directly through the configured
`chrome120` browser impersonation path.

The live CDHS Healthy Choice page says that CDHS is discontinuing implementation
and instructs retailers to make no point-of-sale changes. The three FNS decisions
are therefore retained as a historical, explicitly non-operative decision chain,
not as current purchase policy.

## Generated scope

No retained source, inventory item, provision, coverage row, or source digest was
authored by hand. The repository extractor fetched and generated the scope:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
UV_PROJECT_ENVIRONMENT=/Users/pavelmakarchuk/axiom-corpus-uc/.venv \
uv run --no-sync axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-21-co-snap-policy \
  --manifest manifests/us-co-snap-primary-policy.yaml
```

The retained capture contains 13 files totaling 6,317,575 bytes and generated
598 rows: 13 document roots plus 585 HTML blocks/PDF pages. Coverage is complete at 598 of
598, with no missing, extra, or duplicate citations. The ordered source-hash
aggregate is `8bdcc4bcf74e2f1eefb496e98eff77588232351a939e08a24d910aba284848e0`.

The completed audit observed 6,318,196 bytes and aggregate
`9ed2e5b4ab8e628537976ce489797f7368e13ffb253d7d9d3d157070c9053eef`.
Two consecutive extractions on July 21 produced the retained files, which are
621 bytes smaller while preserving the exact audited 13-root and 585-child row
boundary. A later direct fetch of the outreach page added 207 bytes of volatile
Google Analytics/Tag Manager configuration and preserved the exact same ten
extracted outreach blocks. Tests therefore ratchet the retained capture's bytes
and per-source hashes as artifact-integrity checks; they do not assert that live
HTML wrappers remain byte-stable.

Only after this source-backed replacement is generated, committed, and signed is
the source-less `2026-04-30` inventory/provisions/coverage scope removed. A
separate signed three-file tombstone authenticates those deletions.

## Explicit gaps

- The E&T state-plan PDF prints `FORM STATUS: Unsubmitted`.
- The SNAP page still prints October 2024 income/allotment amounts and conflicting
  ABAWD age descriptions of 18 through 56 and 18 through 64.
- The four FY2026-bound plan/handbook sources end September 30, 2026 and require
  another current-source review after that date.
- Federal law and the broader active CDHS memo catalog remain separate dependency
  scopes; this supporting scope does not claim to replace either boundary.
