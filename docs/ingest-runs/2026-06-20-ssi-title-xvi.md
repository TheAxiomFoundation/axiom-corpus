US SSI Title XVI corpus ingest reasoning

Impact basis:
- PolicyEngine parity ranking over the 2026 US microsimulation identified SSI as the largest pending comparable surface, approximately $65.4B in weighted annual benefits.

Official source:
- US Code Title 42 USLM XML from uscode.house.gov releasepoint Online@119-59.
- Download URL: https://uscode.house.gov/download/releasepoints/us/pl/119/59/xml_usc42@119-59.zip
- USLM metadata: created 2025-12-08; publication Online@119-59.

Scope:
- Ingested only core Title XVI SSI statutory sections instead of full Title 42.
- Sections included: 42 U.S.C. 1381, 1382, 1382a, 1382b, 1382c, 1382d, 1382e, 1382f, 1382g, 1382h, 1382i, 1382j.
- This covers SSI authority/purpose, eligibility and benefit amounts, income, resources, definitions, rehabilitation, state supplementation, COLA, state administration payments, work incentives, medical/social services, and sponsor deeming.

Generated artifact:
- Command used the US Code ingester with repeated --section filters; no corpus rows were written by hand.
- Because full Title 42 USLM XML is too large for normal GitHub review, the ingester wrote a generated scoped USLM source artifact containing only the selected sections while retaining the official download URL in inventory metadata.
- The US Code ingester emitted section rows, first-level subsection rows, and immediate paragraph rows from official USLM identifiers, so encoders can target paths such as `us/statute/42/1382/b` and `us/statute/42/1382a/b/2` without seeing sibling provisions.
- Output run id: 2026-06-20-ssi-title-xvi-title-42.
- Coverage result: complete; 226 source inventory rows matched 226 provision rows.
