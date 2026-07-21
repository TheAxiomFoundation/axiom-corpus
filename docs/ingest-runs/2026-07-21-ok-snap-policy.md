# Oklahoma SNAP policy and cross-chapter dependencies ingest

The current Oklahoma SNAP support scope was generated from ten retained official
sources: six OKDHS appendix PDFs, the Appendix C-3 landing page and complete
1,789-row allotment CSV, and the complete Oklahoma rules API responses for OAC
Title 340 Chapters 2, 10, and 65.

```bash
env -u UV_FROZEN uv run --extra dev axiom-corpus-ingest \
  extract-official-documents \
  --base data/corpus \
  --version 2026-07-21-ok-snap-policy \
  --manifest manifests/us-ok-snap-policy.yaml
```

The extractor retained all 1,018 OAC API records while emitting only the 84
active text-bearing sections selected by the citations and broad section
references in the appendices. The generated scope contains 113 provisions and
has complete coverage with no missing, extra, or duplicate citations.

The OKDHS forms search does not currently publish an Appendix B source object.
The related SNAP formula remains grounded in OAC 340:50-9-1 in the separately
published Chapter 50 regulation scope; no substitute digest or paraphrase was
placed in `official-documents/`.
