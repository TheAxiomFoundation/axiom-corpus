# Ingestion reasoning — us-az/manual/2026-07-12-az-des-faa6-utility-amounts

## Why this document

The SNAP QC administrative-data oracle is expanding to Arizona (922 in-scope
FY2024 reviews, 100% pre-flight ceiling). The 2025-10-30 FAA5 manual ingest
carries the utility-allowance *eligibility* policy
(na-utility-expenses-and-allowances blocks) but not the dollar schedule —
Arizona keeps the amounts in FAA6.J ("Standards, Fees, and Amounts"), section
09 "Utility Allowance Current Amount". Encoding Arizona's FY 2026 standard
utility allowances requires that chart: effective 10/01/2025, SUA $323
(1–3 participants) / $438 (4+), LUA $149 / $201, TUA $44. Arizona sizes the
brackets by *participants* ("Do not count nonparticipants that are coded OU
on SEPA").

## Source mechanics

The live manual (dbmefaapolicy.azdes.gov) sits behind a bot challenge, so the
download rides the Wayback capture of the official URL
(20251030220635id_), the same convention as the 2025-10-30 FAA5 manual
ingest and the FY2024 FNS COLA re-archive (corpus#281). `source_url` remains
the canonical live address. The live DES Nutrition Assistance FAQ page
(des.az.gov, fetched 2026-07-12) states identical amounts, corroborating the
snapshot.

## Notes

- Arizona's FY 2025 chart (archived FAA6.J.09, effective 10/01/2024) showed
  SUA $314/$426, LUA $145/$196, TUA $43 — *below* the FY 2024 values in the
  USDA QC technical documentation (318/431, 150/202, 47). The decrease is
  consistent with the standardized-methodology transition (the November 2024
  HCSUA rule) and does not affect this ingest; the FY 2024 QC replay takes
  its amounts from the QC technical documentation, which the 922-review
  pre-flight already matched empirically.
- OBBBA §10104 (enacted 2025-07-04) bars internet costs from SUAs; the FAA5
  allowable-utility list carries no internet category.
