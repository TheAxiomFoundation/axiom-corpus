# South Dakota SNAP manual ingest

The South Dakota Department of Social Services publishes a single current SNAP
Policy and Procedure Manual PDF. The retained official file identifies itself as
updated July 2026 and contains 339 pages.

The corpus pipeline fetched and extracted the manifest without hand-authored
provision rows:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-21-sd-snap-manual \
  --manifest manifests/us-sd-snap-manual.yaml
```

Result:

- 1 retained official PDF
- 1 document provision and 339 page provisions
- 340 inventory entries matched to 340 provisions
- zero missing, extra, or duplicate citations
- complete coverage

The signed ingest manifest authenticates the retained PDF and all generated
inventory, provision, and coverage artifacts. The focused tests independently
pin the source hash, page count, July 2026 update marker, and generated coverage.
