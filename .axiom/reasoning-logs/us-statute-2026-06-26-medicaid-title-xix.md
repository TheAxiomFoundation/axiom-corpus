US Medicaid Title XIX corpus ingest reasoning

Impact basis:
- PolicyEngine parity work for person-level Medicaid eligibility depends on
  statutory category and income-methodology provisions beyond 42 U.S.C.
  1396a(a)(10).
- Existing RuleSpec Medicaid outputs also cite 42 U.S.C. 1396d(n), but the
  local corpus artifact previously contained only 1396a(a)(10).

Official source:
- US Code Title 42 USLM XML from uscode.house.gov releasepoint Online@119-59.
- Download URL: https://uscode.house.gov/download/releasepoints/us/pl/119/59/xml_usc42@119-59.zip
- USLM metadata: created 2025-12-08; publication Online@119-59.

Scope:
- Replaced the narrow Medicaid Title 42 corpus artifact with exact provision
  paths for the national Medicaid eligibility graph.
- Included 42 U.S.C. 1396a(a)(10), 1396a(e), 1396a(e)(14), 1396a(f), 1396a(l),
  1396a(m), 1396b(v), 1396d(a), 1396d(n), 1396d(p), 1396d(q), 1396p(f), and
  1396u-1 as the USLM citation path `us/statute/42/1396u–1`.
- This adds child, pregnancy, MAGI methodology, 209(b), optional aged/blind/
  disabled, emergency-alien, qualified pregnant woman or child, qualified
  Medicare beneficiary, qualified severely impaired individual, service-category,
  substantial-home-equity, and parent/caretaker statutory source rows for
  follow-on RuleSpec encoding.

Generated artifact:
- Command used the US Code ingester with repeated exact --citation-path filters;
  no corpus rows were written by hand.
- Because full Title 42 USLM XML is too large for normal GitHub review, the
  ingester wrote a generated scoped USLM source artifact containing only the
  selected provisions while retaining the official download URL in inventory
  metadata.
- Output run id: 2026-06-26-medicaid-title-42.
- Coverage result: complete; 107 source inventory rows matched 107 provision
  rows.
