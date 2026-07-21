# Oklahoma SNAP administrative rules ingest

The Oklahoma Secretary of State Office of Administrative Rules application
publishes Oklahoma Administrative Code Title 340, Chapter 50 through its public
production API. The corpus pipeline retained the complete 205-record Chapter 50
response and extracted the 77 active text-bearing SNAP sections without
hand-authored provision rows:

```bash
env -u UV_FROZEN uv run --extra dev axiom-corpus-ingest \
  extract-official-documents \
  --base data/corpus \
  --version 2026-07-21-ok-snap-rules \
  --manifest manifests/us-ok-snap-rules.yaml
```

Result:

- 1 retained official JSON API response
- 1 document provision and 77 active section provisions
- 78 inventory entries matched to 78 provisions
- zero missing, extra, or duplicate citations
- complete coverage

The retained normalized JSON has SHA-256
`8b780c6e3ff25042d379680561271bf204cb5b8aa4dae3d17f756a93fbd944b2`.
The section citation paths, headings, and bodies match the superseded
source-less `2026-05-27-ok-snap-rules` scope exactly. That old scope is removed
only after this source-backed replacement is generated and validated.

Current OKDHS SNAP appendices and OAC sections cited across Chapters 2, 10, and
65 are intentionally retained in a separate policy/dependency scope so the
Chapter 50 regulation remains a coherent primary-source unit.
