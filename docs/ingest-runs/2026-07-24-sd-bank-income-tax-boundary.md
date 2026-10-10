# South Dakota bank income-tax statutory boundary (2026-07-24)

This scope preserves the current official South Dakota Codified Laws chapter
10-43. The Legislature titles that chapter “Income Tax on Banks and Financial
Corporations,” and the chapter's operative imposition section applies to
financial institutions.

This statutory source supplies the higher-authority boundary for the separate
January 2026 Department of Revenue statement that South Dakota has no personal
income tax. It does not transform a bank-franchise or other business or entity
tax into personal income tax and does not independently establish a natural
person's annual resident liability.

Artifacts are generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-24-sd-bank-income-tax-boundary \
  --manifest manifests/us-sd-2026-bank-income-tax-boundary.yaml
```

The archived sources are the official chapter index and the complete text of
section 10-43-2 returned by the Legislature's statute endpoints. The
normalized leaves use the durable legal identities `chapter-index` and
`operative-text`; they do not use ordinal `block-N` fallback paths.
