# Alabama TANF payment-standard and payment-manual sources

Date: 2026-07-02

Purpose: add official Alabama DHR sources needed to encode the Alabama TANF
dollar amount surface after the current administrative-code encoding exposed
that the regulation defines the grant formula but delegates the payment-standard
table to Department-published standards.

Sources:

- Alabama TANF State Plan 2024, official DHR PDF.
  - URL: https://dhr.alabama.gov/wp-content/uploads/2024/09/2024-State-Plan-TANF.pdf
  - HTTP status: 200
  - Last-Modified: 2026-04-15T15:58:13Z
  - ETag: `"69dfb595-3adb3"`
  - Content-Length: 241075
- Alabama DHR Public Assistance Payment Manual, Appendix N, Section 2, official
  DHR PDF.
  - URL: https://dhr.alabama.gov/wp-content/uploads/2022/04/Appendix-N-Sec-2-Public-Assistance-Payment-Manual.pdf
  - HTTP status: 200
  - Last-Modified: 2026-04-15T16:09:33Z
  - ETag: `"69dfb83d-19c0f1"`
  - Content-Length: 1687793

Commands:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-02-al-tanf-official-documents \
  --manifest manifests/us-al-tanf-official-documents.yaml
```

Follow-up:

- Sign the ingest manifest after extraction.
- Run `axiom-corpus-ingest guard-ingested`.
- Use the State Plan payment-standard table together with Alabama Admin Code
  660-2-2-.10, .30, .31, and .32 for the Alabama TANF amount encoding.
