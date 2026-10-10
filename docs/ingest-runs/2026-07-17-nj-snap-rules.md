# New Jersey SNAP regulations corpus ingest

## Official source boundary

The New Jersey Department of Human Services rules-and-regulations page links a
current courtesy copy of the N.J.A.C. 10:87 New Jersey Supplemental Nutrition
Assistance Program manual. DHS states that these copies are not the official New
Jersey Administrative Code publications and that the official Code controls if a
discrepancy exists. The corpus metadata preserves that legal-status qualification.
The retained 570-page PDF states that it includes regulations adopted and published
through New Jersey Register Volume 57, Number 19, dated October 6, 2025. It contains
261 unique codified sections, subchapter notes, and Appendix A.

The manifest pins the official DHS URL, source and compilation dates, page and
section counts, and SHA-256 digest. The current direct source supersedes the prior
current reconstruction. Source-less partial, reconstructed, archived-base, and
rulemaking artifacts are removed with signed tombstones.

## Generated scope

No corpus row is written by hand. The standard manifest-driven extractor retains the
official PDF and segments its complete provision structure:

```bash
env -u UV_FROZEN uv run --extra dev axiom-corpus extract-official-documents \
  --base data/corpus \
  --version 2026-07-17-nj-snap-rules \
  --manifest manifests/us-nj-snap-rules.yaml
```

The generated scope contains one source root plus the chapter notes, 261 codified
sections, two subchapter-notes blocks, and Appendix A, for complete 266-of-266
coverage. A second live extraction produced the same aggregate artifact digest
`3bd4a365b1e03ad7552ce3679753c29502e210ae91ee17b18bfd95c89ea6222a`.
