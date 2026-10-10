Ingest the per-revision USITC HTS notes documents (General Note 3 and
Chapter 99 PDFs) for 2026 Revisions 3, 4, and 12 — the three releases in
the US tariff parity window whose full snapshots were ingested by the T0
run but whose notes documents were not covered by the 44-release gapfill.
Three `extract-official-documents` versions under `us/statute`, each
pinned to release-specific PDFs from the USITC `reststop/file` endpoint
with citation paths `us/statute/hts/general-note-3` and
`us/statute/hts/chapter-99`. Completes per-revision notes coverage for
every release in the parity window.
