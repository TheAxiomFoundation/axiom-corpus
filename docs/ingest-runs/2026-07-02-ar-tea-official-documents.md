# Arkansas TEA official payment and eligibility sources

Date: 2026-07-02

Purpose: add official Arkansas DHS sources needed to encode the Arkansas
Transitional Employment Assistance payment and eligibility surface for
PolicyEngine parity. Arkansas Code public access currently routes through
Lexis/CAPTCHA per the state-statute source queue, so this run uses official
DHS implementation documents as the best available primary administrative
sources for the computable TEA benefit formula.

Sources:

- Arkansas DHS Transitional Employment Assistance Policy Manual, official DHS
  PDF dated 10/1/2024.
  - URL: https://humanservices.arkansas.gov/wp-content/uploads/TEA_MANUAL-10.1.24.pdf
  - HTTP status: 200
  - Last-Modified: 2024-10-07T14:14:42Z
  - ETag: `"6703ecd2-179181"`
  - Content-Length: 1544577
- Arkansas DHS Transitional Employment Assistance Quick Reference, official
  DHS PDF effective 04/01/2024.
  - URL: https://humanservices.arkansas.gov/wp-content/uploads/TEA-Quick-Reference-Guide-4.2024.pdf
  - HTTP status: 200
  - Last-Modified: 2026-04-09T19:01:26Z
  - ETag: `"69d7f786-1e66d"`
  - Content-Length: 124525
- Arkansas DHS Public Notice, TEA Income Limit Increase, official DHS PDF dated
  10/7/2022.
  - URL: https://humanservices.arkansas.gov/wp-content/uploads/Public-Notice-TEA-Income-Limit-Increase.pdf
  - HTTP status: 200
  - Last-Modified: 2024-10-07T14:17:19Z
  - ETag: `"6703ed6f-b75c2"`
  - Content-Length: 751042

Commands:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-02-ar-tea-official-documents \
  --manifest manifests/us-ar-tea-official-documents.yaml
```

Follow-up:

- Sign the ingest manifest after extraction.
- Run `axiom-corpus-ingest guard-ingested`.
- Use TEA Manual sections 2101, 2351, 2352, 2353.1, 2353.2, 2361,
  and 2362 for the Arkansas TEA amount and eligibility encoding.
