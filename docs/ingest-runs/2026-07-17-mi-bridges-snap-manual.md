# Michigan Bridges SNAP manual corpus ingest

## Official source boundary

Michigan publishes cash, child care, medical, food, and emergency-relief policy in a
combined Bridges manual. The MDHHS HTML landing page currently presents "Future Policy
Manuals" and links to the `/exF/` tree, so it is not authoritative for this capture. The
retained BAM, BEM, RFT, and RFS PDF tables of contents under `/OLMWeb/ex/` define the
current-effective source boundary. On 2026-07-17, `/exF/` already contained 2026-08-01
revisions, so this scope uses only `/OLMWeb/ex/` documents effective on or before the
capture date.

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
95 of the 196 documents are explicitly marked as SNAP-bearing.

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
`941a4394d8e6b31dee3241068c3dfb2c99afa7a9ec6fb03a3c1ce72731e6622a`.

The superseded `2026-05-27-mi-bridges-manual` scope had 2,069 derived rows but retained none
of its 186 referenced source files. It is removed only after this source-backed replacement
is committed and signed.
