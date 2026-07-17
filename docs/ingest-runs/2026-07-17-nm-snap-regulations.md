# New Mexico SNAP regulations corpus ingest

## Official source boundary

The New Mexico State Records Center and Archives publishes the New Mexico
Administrative Code and states that the current compilation includes rules effective
on or before July 1, 2026. The Health Care Authority Income Support Division page
links the ten Chapter 100 general public-assistance parts used by SNAP. The official
SRCA Chapter 139 index supplies eighteen Food Stamp Program parts, including the
repealed Part 640 and Part 650 pages retained as zero-provision source roots.

The manifest retains all 28 official HTML documents and pins each source URL, byte
count, SHA-256 digest, NMAC citation, and extracted provision count. The prior
source-less scope contained 330 sections. Its colon-only heading pattern silently
omitted 30 codified headings, including reserved ranges, uppercase headings without
colons, and `8.139.502.8`, whose label is split across nested HTML spans. The current
extractor restores those headings and independently matches every retained source
label.

## Generated scope

No corpus row is written by hand. The standard manifest-driven extractor retains the
official HTML and segments the complete provision structure:

```bash
env -u UV_FROZEN uv run --extra dev axiom-corpus extract-official-documents \
  --base data/corpus \
  --version 2026-07-17-nm-snap-regulations \
  --manifest manifests/us-nm-snap-regulations.yaml
```

The generated scope contains 28 source roots plus 360 codified sections and has
complete 388-of-388 coverage. A second live extraction produced the same aggregate
artifact digest
`6b40423674e3bbf4806f1a7921939f39a19342a83d1a9f65a08a29295fceb0a9`.

The superseded `2026-05-27-nm-snap-regulations` scope retains no official source
files. It is removed only after this source-backed replacement is committed and
signed.
