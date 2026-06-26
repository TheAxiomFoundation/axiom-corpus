US CHIP Title XXI corpus ingest reasoning

Impact basis:
- PolicyEngine parity encoding for CHIP referenced Title XXI provisions that
  were present through Supabase fallback but absent from the local JSONL corpus
  inventory.

Official source:
- US Code Title 42 USLM XML from uscode.house.gov releasepoint Online@119-99.
- Download URL: https://uscode.house.gov/download/releasepoints/us/pl/119/99/xml_usc42@119-99.zip
- USLM metadata: created 2026-04-17; publication Online@119-99.

Scope:
- Ingested the CHIP Title XXI statutory sections in 42 U.S.C. 1397aa through
  1397mm.
- Sections included: 42 U.S.C. 1397aa, 1397bb, 1397cc, 1397dd, 1397ee,
  1397ff, 1397gg, 1397hh, 1397ii, 1397jj, 1397kk, 1397ll, and 1397mm.
- This includes the blocker paths 42 U.S.C. 1397bb, 1397cc, 1397jj, and
  1397ll, plus the surrounding CHIP plan, allotment, payment, approval,
  reporting, definitions, and outreach sections.

Generated artifact:
- Command used the US Code ingester with repeated --section filters and
  --include-title; no corpus rows were written by hand.
- Because full Title 42 USLM XML is too large for normal GitHub review, the
  ingester wrote a generated scoped USLM source artifact containing only the
  selected sections while retaining the official download URL in inventory
  metadata.
- The US Code ingester emitted the Title 42 container, section rows,
  first-level subsection rows, and immediate paragraph rows from official USLM
  identifiers.
- Output run id: 2026-06-26-chip-title-xxi-title-42.
- Coverage result: complete; 399 source inventory rows matched 399 provision
  rows.
