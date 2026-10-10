# Georgia individual-income-tax primary sources (2026-07-21)

This recovery adds three complementary Georgia scopes for RuleSpec
individual-income-tax proofs:

- `2026-07-21-ga-ocga-title-48-release86-us-ga-title-48` is a historical
  O.C.G.A. Title 48 snapshot as of 2022-11-01. The ODT is the raw
  state-released file preserved in Archive.org item `gov.ga.ocga.2018` by
  Public.Resource.Org. Archive.org provides archival custody; it is not the
  originating legal publisher. The source file is pinned at SHA-256
  `bc15945bc27c1bc238d29f81c0e8b036592e26f95ea101ce3169963a772c8224`.
  The scope is explicitly historical and must not be described as the current
  consolidated Georgia Code in 2026.
- `2026-07-21-ga-pit-session-laws` contains the official signed PDFs for 2023
  SB 56 (Act 236), 2024 HB 1021 (Act 377), 2025 HB 136 (Act 182), and 2026
  HB 463 (Act 465). These acts establish the post-snapshot income-tax
  transitions used by the current PIT program. The base act citations are
  structural parents; the extracted act text is carried by the corresponding
  `/document-1` citations.
- `2026-07-21-ga-it-511-2025` contains the official Georgia Department of
  Revenue 2025 IT-511 Individual Income Tax Booklet. Its text-bearing
  `us-ga/form/it-511/2025/document-1` provision includes the low-income credit
  worksheet and its age-65 exemption instructions. The manifest forces
  300-DPI OCR through the corpus extractor's standard local Tesseract CLI
  because the worksheet rows are vector outlines rather than PDF text.

The historical Title 48 source was already fetched to the manifest-pinned,
ignored input location before extraction:

```bash
data/statutes/us-ga/release86.2022.11/gov.ga.ocga.title.48.odt
```

Artifacts were generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-state-statutes \
  --base data/corpus \
  --manifest manifests/us-ga-ocga-title-48-release86.yaml

uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-21-ga-pit-session-laws \
  --manifest manifests/us-ga-pit-session-laws-official-documents.yaml

uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-21-ga-it-511-2025 \
  --manifest manifests/us-ga-it-511-2025-official-document.yaml
```

All runs write the canonical four artifact families under `sources/`,
`inventory/`, `provisions/`, and `coverage/`. The successor release selector
`us-rulespec-2026-07-21-ga-pit-current` remains unpublished.

The Title 48 snapshot adds 25 canonical citation identities with uppercase
segments, principally verbatim letter-suffixed Georgia chapter and section
labels such as `48-7A-3`. The citation-path irregular-family ceiling therefore
moves from 6,291 to the measured 6,316; no existing path was rewritten.
