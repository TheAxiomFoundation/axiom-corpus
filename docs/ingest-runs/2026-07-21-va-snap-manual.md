# Virginia SNAP manual ingest

The Virginia Department of Social Services publishes a single current SNAP
Full Manual PDF. The retained 714-page official file incorporates SNAP Manual
Transmittal 36, issued September 18, 2025 and generally effective October 1,
2025. The transmittal identifies specified Public Law 119-21 provisions as
effective November 1, 2025.

The corpus pipeline fetched and extracted the manifest without hand-authored
provision rows. Tesseract must be available on `PATH` for OCR fallback on
image-only pages:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-21-va-snap-manual \
  --manifest manifests/us-va-snap-manual.yaml
```

Result:

- 1 retained official PDF
- 1 document provision and 677 page provisions
- all 675 text-bearing pages extracted natively
- both image-only appendix pages extracted through OCR fallback
- 37 truly blank separator pages omitted
- 678 inventory entries matched to 678 provisions
- zero missing, extra, or duplicate citations
- complete coverage

The signed ingest manifest authenticates the retained PDF and all generated
inventory, provision, and coverage artifacts. Focused tests independently pin
the source hash, page count, transmittal dates, represented page set, OCR output,
and generated coverage.
