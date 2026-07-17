# New Jersey SNAP regulations corpus ingest

## Official source boundary

The New Jersey Department of Human Services rules-and-regulations page links the
current N.J.A.C. 10:87 New Jersey Supplemental Nutrition Assistance Program manual.
The retained 570-page PDF states that it includes regulations adopted and published
through New Jersey Register Volume 57, Number 19, dated October 6, 2025. It contains
261 unique codified sections, subchapter notes, and Appendix A.

The manifest pins the official DHS URL, source and compilation dates, page and
section counts, and SHA-256 digest. The current direct source supersedes the prior
current reconstruction; the archived 2017 base and later rulemaking scopes remain
available as historical evidence.

## Generated scope

No corpus row is written by hand. The standard manifest-driven extractor retains the
official PDF and segments its complete provision structure:

```bash
env -u UV_FROZEN uv run --extra dev axiom-corpus extract-official-documents \
  --base data/corpus \
  --version 2026-07-17-nj-snap-rules \
  --manifest manifests/us-nj-snap-rules.yaml
```

The generated scope contains one source root plus 261 codified sections, two
subchapter-notes blocks, and Appendix A, for complete 265-of-265 coverage. The
second live extraction produced the same aggregate artifact digest
`b933cb361c43daa21bcf2795cdc74efe34d5f01ca84e58dff414c0a5051ab755`.
