# Louisiana Title 47 status re-extraction

This scope re-fetches and re-extracts Louisiana Revised Statutes Title 47 from
the official Louisiana Legislature HTML pages as of July 22, 2026. No source
text is rewritten.

The re-extraction follows the Louisiana adapter correction merged in corpus
PR #467. Whole-section repeal and expiration status is now derived from the
section heading, while body text describing a repealed subsection or amendment
history does not mark the entire section repealed. Bodyless range tombstones
remain classified from their official headings.

The generated scope is
`us-la/statute/2026-07-22-la-title-47-official-current-us-la-title-47` and
contains 2,664 source inventory items and 2,664 normalized provisions with
complete coverage. R.S. 47:32 is active and retains its operative three percent
individual income-tax rate; R.S. 47:9 remains a repealed whole-section
tombstone.

The successor release selector replaces the prior Title 47 scope and removes
the separate four-row Louisiana recovery carrier. Its four sections, R.S.
47:294, 47:295, 47:297.4, and 47:297.8, are present in the complete replacement
scope, so the selector remains collision-free.

Extraction command:

```bash
uv run --extra dev axiom-corpus-ingest extract-state-statutes \
  --base data/corpus \
  --manifest manifests/us-la-title-47-status-reextract.yaml \
  --only-source-id us-la-revised-statutes-title-47
```

Validation includes signed-ingest manifest verification, tracked-scope
verification, generated-artifact guarding, complete scope coverage, and deep
validation of the 198-scope successor release.
