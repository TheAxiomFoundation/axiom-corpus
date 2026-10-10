# New Mexico SNAP regulations corpus ingest

## Official source boundary

The New Mexico State Records Center and Archives publishes the New Mexico
Administrative Code and states that the current compilation includes rules effective
on or before July 1, 2026. The Health Care Authority Income Support Division page
lists the ten Chapter 100 general public-assistance parts used by SNAP and eighteen
Chapter 139 Food Stamp Program parts. Part 640 appears as an unlinked citation on
that official HCA index; its corresponding official SRCA page and the linked
repealed Part 650 page are retained as zero-provision source roots.

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
`4608558e70473c976b6454c9d582af71c5a21f52f467e4d5946147c5ce906d8c`.

The superseded `2026-05-27-nm-snap-regulations` scope retains no official source
files. It is removed only after this source-backed replacement is committed and
signed.
