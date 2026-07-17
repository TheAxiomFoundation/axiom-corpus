# Michigan Bridges SNAP manual corpus ingest

## Official source boundary

Michigan publishes cash, child care, medical, food, and emergency-relief policy in a
combined Bridges manual. The current-effective MDHHS tree at
`https://mdhhs-pres-prod.michigan.gov/OLMWeb/ex/html/` is distinct from the future-effective
`/exF/` tree. On 2026-07-17, the future tree already contained 2026-08-01 revisions, so this
scope uses only `/OLMWeb/ex/` documents effective on or before the capture date.

The retained source set contains:

- the current Bridges policy bulletin log;
- both official BAM and BEM tables of contents;
- all 55 BAM and 128 BEM chapters listed in those tables of contents;
- the Bridges policy glossary;
- RFT 250, 255, 260, 262, and 295, plus the RFT table of contents;
- RFS 305, plus the RFS table of contents; and
- RFT 248, retained as part of the pre-existing combined-manual source boundary, but
  explicitly marked as not containing SNAP policy.

The manifest records each PDF's effective date, policy bulletin revision, SHA-256 digest,
and SNAP applicability. The full combined manual is retained to avoid dropping shared rules;
97 of the 196 documents are explicitly marked as SNAP-bearing.

## Generated scope

No corpus row was written by hand. The standard manifest-driven extractor generated the
scope:

```bash
env -u UV_FROZEN uv run --extra dev axiom-corpus extract-official-documents \
  --base data/corpus \
  --version 2026-07-17-mi-bridges-manual \
  --manifest manifests/us-mi-bridges-manual.yaml
```

The run retained 196 official PDFs and generated 2,310 rows: 196 document roots and 2,114
PDF page rows. Coverage is complete at 2,310 of 2,310, with no missing or extra provisions.
A second full extraction produced the same aggregate artifact digest
`bde4d3ea20e970003acbf26be18fae13e1d23e503a3fc76f6f33b2a12f4ba922`.

The superseded `2026-05-27-mi-bridges-manual` scope had 2,069 derived rows but retained none
of its 186 referenced source files. It is removed only after this source-backed replacement
is committed and signed.
