# Nebraska SNAP regulations corpus ingest

## Official source boundary

Nebraska publishes the Supplemental Nutrition Assistance Program rules as Title 475
of the Nebraska Administrative Code. The official rules API listed five current
chapters on July 17, 2026: general provisions, household processing, eligibility,
benefits, and Electronic Benefits Transfer card issuance and accountability. The
manifest retains the official filed PDF for chapter 1 and the current official rules
PDFs for chapters 2 through 5. It records the API chapter identifiers, effective and
filed dates, source blob names, page counts, provision counts, and SHA-256 hashes.

The five PDFs contain 156 pages and 737 unique labeled provisions. The chapter 1 PDF
is effective December 24, 2025; chapters 2 through 4 are effective September 17,
2024; and chapter 5 is effective July 4, 2020. No expired or future-effective chapter
is included.

## Generated scope

No corpus row is written by hand. The standard manifest-driven extractor retains the
five official PDFs and segments their complete labeled provision hierarchy:

```bash
env -u UV_FROZEN uv run --extra dev axiom-corpus extract-official-documents \
  --base data/corpus \
  --version 2026-07-17-ne-snap-rules \
  --manifest manifests/us-ne-snap-rules.yaml
```

The generated scope contains five source roots plus 737 sections and has complete
742-of-742 coverage. A second live extraction produced the same aggregate artifact
digest `6f7a0a26665aa68298bb31ae8ccbd7e22c15842ad290763583fcf6a02e005cc8`.

The superseded `2026-05-27-ne-snap-rules` scope contains ten derived rows but retains
none of its five referenced source files. It is removed only after this source-backed
replacement is committed and signed.
