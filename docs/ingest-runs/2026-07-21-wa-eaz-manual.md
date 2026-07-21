# Washington EA-Z Manual ingest

## Source boundary

The Washington Department of Social and Health Services current Eligibility A-Z
(EA-Z) Manual book tree contains 203 links. Three are companion sources outside
this scope: the EA-Z revision history, notification-of-rule-changes page, and
WAC rules index. The remaining 200 ordered links exactly match the retained
manual-page manifest. Their ordered URL digest is
`4b2eaaae9969afdca2d4aa2edb5984fca75f8bf26e9cf303a4f45aa3cc527a44`.

This scope is complete for the current 200-page EA-Z HTML manual, but it is not
complete Washington SNAP legal authority. The three companion pages, the WAC
chapters referenced by the index, federal SNAP statutes and regulations, and
linked forms and desk aids remain explicit follow-up source scopes.

## Generated scope

No retained source or corpus row was authored by hand. The repository's
official-document extractor fetched and generated the scope:

```bash
env -u UV_FROZEN uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-21-wa-eaz-manual \
  --manifest manifests/us-wa-eaz-manual.yaml
```

The run retained 200 official HTML responses totaling 20,353,997 bytes. The
ordered concatenation of their inventory SHA-256 values has SHA-256 digest
`91b5cbd4bd138f2a612379b6cbc0743dec0513830c6dbc94127bb8ac64c0966a`.
It generated 1,265 rows: 200 document roots and 1,065 content blocks. Coverage
is complete at 1,265 of 1,265, with no missing, extra, or duplicate citation
paths.

The superseded `2026-05-27-wa-eaz-manual` scope has the same row count but
retained none of its referenced source files. Its three derived artifacts are
removed only after this source-backed replacement is generated, committed, and
signed, with those removals authenticated by its signed ingest tombstone.
