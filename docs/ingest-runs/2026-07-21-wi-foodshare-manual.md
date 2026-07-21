# Wisconsin FoodShare handbook ingest

The Wisconsin Department of Health Services publishes the current FoodShare
Wisconsin Handbook as Release 26-01. The retained official PDF contains 372
text-bearing pages and identifies changed sections as released and effective
April 15, 2026. The online handbook header displays 2025, but its linked PDF and
release identifier establish that the header year is a typo.

The corpus pipeline fetched and extracted the manifest without hand-authored
provision rows:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-21-wi-foodshare-manual \
  --manifest manifests/us-wi-foodshare-manual.yaml
```

Result:

- 1 retained official PDF
- 1 document provision and 372 page provisions
- every PDF page contains native extractable text
- 373 inventory entries matched to 373 provisions
- zero missing, extra, or duplicate citations
- complete coverage

The signed ingest manifest authenticates the retained PDF and all generated
inventory, provision, and coverage artifacts. Focused tests independently pin
the source hash, page count, release markers, represented page set, and coverage.
