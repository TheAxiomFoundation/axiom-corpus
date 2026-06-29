US Medicaid 42 CFR Part 435 corpus ingest reasoning

Impact basis:
- PolicyEngine parity work for Medicaid eligibility depends heavily on
  eligibility-group, residency, citizenship, MAGI, medically needy, and related
  Medicaid agency rules in 42 CFR Part 435.
- RuleSpec encoders need section-level CFR source rows so each regulation can
  be encoded from primary eCFR text rather than from PolicyEngine formulas.

Official source:
- eCFR Title 42 Part 435 source XML and structure JSON from the official eCFR
  bulk/current feed.
- Source date: 2026-06-25.

Scope:
- Ingested current 42 CFR Part 435 as a section-level regulation corpus scope.
- This includes national Medicaid eligibility provisions used by existing
  RuleSpec encodings, including categories of eligibility, optional groups,
  MAGI household and income methodology, medically needy rules, eligibility
  factor rules, and work-requirement sections.

Generated artifact:
- Command used the eCFR ingester scoped to Title 42 Part 435; no corpus rows
  were written by hand.
- Output run id: 2026-06-25-title-42-part-435.
- Coverage result: complete; 168 source inventory rows matched 168 provision
  rows.
