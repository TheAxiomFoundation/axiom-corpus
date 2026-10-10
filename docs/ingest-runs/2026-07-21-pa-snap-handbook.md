# Pennsylvania SNAP Handbook ingest

## Source boundary

The Pennsylvania Department of Human Services current SNAP Handbook table of
contents expands to 297 official HTML topics across 33 handbook families. This
scope retains every one of those topic pages as fetched on July 21, 2026. The
ordered concatenation of the 297 source SHA-256 values has SHA-256 digest
`98aadcd8f4cd9e3da755eb7efb59851984e615d0d8996425a5d6f41b88f7fc02`.

This boundary is complete for the current HTML handbook, but it is not complete
Pennsylvania SNAP legal authority. Pennsylvania Code Chapter 501, substantive
attachments linked from the operations-memorandum and policy-clarification
catalogs, and dependencies in other program manuals remain explicit follow-up
source scopes.

## Generated scope

No retained source or corpus row was authored by hand. The repository's
official-document extractor fetched and generated the scope:

```bash
env -u UV_FROZEN uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-21-pa-snap-handbook \
  --manifest manifests/us-pa-snap-handbook.yaml
```

The run retained 297 official HTML snapshots totaling 5,095,767 bytes. It
generated 1,055 rows: 297 document roots and 758 content blocks. Coverage is
complete at 1,055 of 1,055, with no missing, extra, or duplicate citation paths.

The superseded `2026-05-27-pa-snap-handbook` scope contains the same row count
but retained none of its referenced source files. Its three derived artifacts
are removed only after the source-backed replacement is generated, committed,
and signed, with those removals authenticated by its signed ingest tombstone.
