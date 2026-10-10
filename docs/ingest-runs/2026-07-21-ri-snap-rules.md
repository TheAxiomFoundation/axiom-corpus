# Rhode Island SNAP regulation ingest

The Rhode Island Department of State publishes the current Department of Human
Services SNAP regulation, 218-RICR-20-00-1, as a signed 272-page PDF. The agency
signed the amendment March 13, 2026, the Department of State signed it March 16,
2026, and the regulation became effective April 5, 2026.

The earlier HTML manifest collapsed the entire regulation into one body. This
ingest instead follows the official page's Download Regulation link and uses the
corpus PDF path to preserve page-level source anchors. No provision rows were
hand-authored:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-21-ri-snap-rules \
  --manifest manifests/us-ri-snap-rules.yaml
```

Result:

- 1 retained official signed PDF
- 1 document provision and 272 page provisions
- every PDF page contains native extractable text
- 273 inventory entries matched to 273 provisions
- zero missing, extra, or duplicate citations
- complete coverage

The signed ingest manifest authenticates the retained PDF and all generated
inventory, provision, and coverage artifacts. Focused tests independently pin
the source hash, page count, official signing/effective dates, page set, and
coverage.
