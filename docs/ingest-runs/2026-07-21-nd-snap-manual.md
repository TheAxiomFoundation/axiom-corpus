# North Dakota SNAP Policy Manual Release 26.5

## Scope

- Jurisdiction: `us-nd`
- Document class: `manual`
- Version: `2026-07-21-nd-snap-manual`
- Program: SNAP
- Authority: North Dakota Health and Human Services

## Official Sources

The scope retains the official manual landing page, the live JavaScript table of
contents, the four-page Release 26.5 update PDF, and all 64 manual topic pages.
The landing page identifies Release 26.5 as published June 15, 2026, and the
release log identifies the same effective date.

The live TOC matched the 64 existing topic URLs, titles, and order exactly.
Existing topic source IDs and citation paths were retained to avoid identity
churn. The refreshed section 301 classifies Job Retention as a non-qualifying
E&T component. The official section 1002 HTML contains the malformed strings
`eligibleClosed` and `Able-bodiedClosed`; the source snapshot preserves those
upstream bytes without correction.

## Generation

```bash
env -u UV_FROZEN uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-21-nd-snap-manual \
  --manifest manifests/us-nd-snap-manual.yaml
```

The pipeline retained 67 source files and generated 167 provisions: 67 document
records, 96 HTML/JavaScript blocks, and four PDF page records. Coverage is
complete at 167/167 with no missing, extra, or duplicate citations. No
provision rows were hand-authored.
