# Mississippi SNAP policy manual corpus ingest

## Official source boundary

The Mississippi Department of Human Services SNAP page and Administrative Codes page both
link Part 14 of Title 18 to the same Secretary of State PDF. That filed manual is revised
December 20, 2025 and contains Chapters 1 through 35, including regular SNAP, E&T, ABAWD,
ESAP, MSCAP, EBT, replacement benefits, and D-SNAP policy.

An official MDHS upload at
`https://www.mdhs.ms.gov/wp-content/uploads/2026/07/SNAP-Policy-Manual-May-2026-1.pdf`
was also observed. Its cover says revised May 1, 2026, but neither current MDHS landing page
links it and the Secretary of State still serves the December filing. It is therefore
recorded as source drift and excluded from this operative scope until an official page
designates it as current.

The retained Secretary of State PDF has SHA-256
`1093741e8c95d9b60ea5499242a43dcd07cb9433aaca1de88c82b719a6498764`.

## Generated scope

No corpus row is written by hand. The standard manifest-driven extractor generates the
scope and uses the PDF's bold italic rule headings to distinguish 384 actual rules from
identically worded in-body cross-references:

```bash
env -u UV_FROZEN uv run --extra dev axiom-corpus extract-official-documents \
  --base data/corpus \
  --version 2026-07-17-ms-snap-policy-manual \
  --manifest manifests/us-ms-snap-manual.yaml
```

The superseded `2026-05-27-ms-snap-manual` scope contains 169 derived page rows but does
not retain its referenced PDF. It is removed only after this source-backed replacement is
committed and signed.
